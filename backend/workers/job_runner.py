"""
Job runner — orchestrates the full pipeline for one search job.

Pipeline:
  1. Parse query → intent
  2. OSM discovery (3 parallel strategies) + Wikidata SPARQL  ← run together
  3. URL guessing for named no-site OSM entities (BEFORE bulk-save)
  4. Batch-save entities that still have no website
  5. Parallel crawl all discovered URLs (OSM+guessed+Wikidata+web)
  6. Finalize job status
"""
import asyncio
import re
from typing import Optional
from loguru import logger

from storage.database import AsyncSessionLocal
from storage import crud
from query_engine.parser import parse_query
from discovery_engine.osm_discovery import osm_discovery
from discovery_engine.wikidata_discovery import wikidata_discover
from discovery_engine.web_discovery import web_discovery, _guess_urls
from discovery_engine.deduplicator import Deduplicator, is_valid_url
from crawler_engine.http_crawler import crawl_site
from core.config import settings

_BATCH_SIZE = 100


async def _pause_checkpoint(job_id: int) -> bool:
    """Poll DB while job is paused. Returns True to continue, False to abort."""
    while True:
        async with AsyncSessionLocal() as db:
            job = await crud.get_job(db, job_id)
        if not job or job.status in ("done", "failed"):
            return False
        if job.status != "paused":
            return True
        await asyncio.sleep(2)


# ── helpers ───────────────────────────────────────────────────────────────────

async def _bulk_save(db, job_id: int, entities: list[dict], entity_type: str, source: str):
    """Insert entities in batches and push live result_count every batch."""
    for i, entity in enumerate(entities):
        name = entity.get("name")
        if not name:
            continue
        await crud.insert_lead(db, {
            "job_id":     job_id,
            "name":       name,
            "category":   entity_type,
            "website":    entity.get("website") or None,
            "email":      entity.get("email") or None,
            "phone":      entity.get("phone") or None,
            "address":    entity.get("address") or None,
            "source_url": entity.get("website") or None,
            "source":     source,
        })
        if (i + 1) % _BATCH_SIZE == 0:
            await db.commit()
            _, count = await crud.get_leads(db, job_id=job_id, page=1, page_size=1)
            await crud.update_job_status(db, job_id, "running", result_count=count)
            await db.commit()
    await db.commit()


async def _crawl_and_save(
    job_id: int,
    url: str,
    prefill: Optional[dict],
    entity_type: str,
    semaphore: asyncio.Semaphore,
):
    """Crawl one URL and save the lead in its own DB session to avoid cross-task contamination."""
    async with semaphore:
        logger.info(f"Crawling: {url}")
        try:
            data = await crawl_site(url)
        except Exception as exc:
            logger.warning(f"Crawl error {url}: {exc}")
            data = {}

        merged = dict(prefill) if prefill else {}
        for k, v in data.items():
            if v and not merged.get(k):
                merged[k] = v

        name = merged.get("name") or (url.split("//")[-1].split("/")[0] if url else None)
        if not name:
            return

        try:
            async with AsyncSessionLocal() as session:
                await crud.insert_lead(session, {
                    "job_id":      job_id,
                    "name":        name,
                    "category":    entity_type,
                    "description": merged.get("description"),
                    "website":     url,
                    "email":       merged.get("email"),
                    "phone":       merged.get("phone"),
                    "address":     merged.get("address"),
                    "facebook":    merged.get("facebook"),
                    "instagram":   merged.get("instagram"),
                    "linkedin":    merged.get("linkedin"),
                    "twitter":     merged.get("twitter"),
                    "youtube":     merged.get("youtube"),
                    "source_url":  url,
                    "source":      "web_crawl",
                })
                await session.commit()
        except Exception as exc:
            logger.warning(f"DB save failed for {url}: {exc}")


async def _guess_url_for_entity(entity: dict, location: str, sem: asyncio.Semaphore) -> str | None:
    """Try to resolve a website for a named entity via URL guessing."""
    name = entity.get("name") or ""
    slug = re.sub(r"[^a-z0-9]", "", name.lower())
    if len(slug) < 5:
        return None
    async with sem:
        urls = await _guess_urls(name, location)
        return urls[0] if urls else None


# ── main pipeline ─────────────────────────────────────────────────────────────

async def run_job(job_id: int, exclude_existing: bool = False):
    async with AsyncSessionLocal() as db:
        try:
            job = await crud.get_job(db, job_id)
            if not job:
                return

            await crud.update_job_status(db, job_id, "running")
            await db.commit()

            # ── 1. Parse ───────────────────────────────────────────────────
            intent = parse_query(job.query)
            logger.info(
                f"Job {job_id}: entity={intent.entity_type!r}, location={intent.location!r}, "
                f"exclude_existing={exclude_existing}"
            )

            # ── 1b. Pre-load existing data for cross-job dedup ─────────────
            existing_names: set[str] = set()
            existing_websites: set[str] = set()
            if exclude_existing:
                existing_names, existing_websites = await crud.get_existing_names_websites(db)
                logger.info(
                    f"Job {job_id}: excluding {len(existing_names)} known names, "
                    f"{len(existing_websites)} known websites"
                )

            # ── 2. Discovery (OSM multi-strategy + Wikidata, parallel) ─────
            osm_task = osm_discovery.discover(intent.entity_type, intent.location)
            wd_task  = wikidata_discover(intent.entity_type, intent.location)
            raw = await asyncio.gather(osm_task, wd_task, return_exceptions=True)

            osm_entities = raw[0] if isinstance(raw[0], list) else []
            wd_entities  = raw[1] if isinstance(raw[1], list) else []

            if isinstance(raw[0], Exception):
                logger.error(f"Job {job_id}: OSM discovery failed: {raw[0]}")
            if isinstance(raw[1], Exception):
                logger.error(f"Job {job_id}: Wikidata discovery failed: {raw[1]}")

            logger.info(
                f"Job {job_id}: OSM={len(osm_entities)}, Wikidata={len(wd_entities)}"
            )

            if not await _pause_checkpoint(job_id):
                return

            # Global name deduplication across all sources
            global_dedup = Deduplicator()
            # Pre-seed with existing names so we skip already-known leads
            for name in existing_names:
                global_dedup.add_name(name)

            # Classify OSM entities
            osm_with_site:    list[dict] = []
            osm_without_site: list[dict] = []
            for e in osm_entities:
                global_dedup.add_name(e["name"])
                if e.get("website") and is_valid_url(e["website"]):
                    osm_with_site.append(e)
                else:
                    osm_without_site.append(e)

            # Classify Wikidata entities (skip if already seen by name)
            wd_with_site:    list[dict] = []
            wd_without_site: list[dict] = []
            for e in wd_entities:
                if global_dedup.is_new_name(e["name"]):
                    global_dedup.add_name(e["name"])
                    if e.get("website") and is_valid_url(e["website"]):
                        wd_with_site.append(e)
                    else:
                        wd_without_site.append(e)

            # ── 3. URL guessing (BEFORE bulk-save to avoid double-saving) ──
            # guess_dedup is local to this phase — prevents duplicate guessed
            # URLs from entering osm_with_site. url_dedup (used in step 6 for
            # the full crawl queue) is initialized fresh so guessed URLs
            # are NOT pre-marked as seen, meaning they DO get crawled.
            guess_candidates = [
                e for e in osm_without_site
                if len(re.sub(r"[^a-z0-9]", "", e["name"].lower())) >= 5
            ][:300]

            guessed_names: set[str] = set()

            if guess_candidates:
                guess_dedup = Deduplicator()   # separate from url_dedup
                guess_sem = asyncio.Semaphore(10)
                guess_tasks = [
                    _guess_url_for_entity(e, intent.location, guess_sem)
                    for e in guess_candidates
                ]
                guessed_urls_list = await asyncio.gather(*guess_tasks, return_exceptions=True)
                hits = 0
                for entity, guessed_url in zip(guess_candidates, guessed_urls_list):
                    if guessed_url and isinstance(guessed_url, str) and is_valid_url(guessed_url):
                        if guess_dedup.is_new(guessed_url):
                            guess_dedup.add(guessed_url)
                            osm_with_site.append({**entity, "website": guessed_url})
                            guessed_names.add(entity["name"])
                            hits += 1
                logger.info(f"Job {job_id}: URL guessing — {hits} hits / {len(guess_candidates)} tried")

            if not await _pause_checkpoint(job_id):
                return

            # ── 4. Batch-save entities that still have no website ──────────
            # Exclude entities whose URL was just guessed — they'll be crawled.
            truly_no_site = [
                e for e in osm_without_site if e["name"] not in guessed_names
            ] + wd_without_site

            if truly_no_site:
                await _bulk_save(db, job_id, truly_no_site, intent.entity_type, "osm")
                logger.info(f"Job {job_id}: saved {len(truly_no_site)} no-website entities")

            # Push live progress
            _, running_count = await crud.get_leads(db, job_id=job_id, page=1, page_size=1)
            await crud.update_job_status(db, job_id, "running", result_count=running_count)
            await db.commit()

            # ── 5. Web discovery (DDG supplementary) ──────────────────────
            web_urls: list[dict] = []
            if intent.location:
                web_urls = await web_discovery.discover(
                    intent.search_queries(),
                    max_urls=settings.MAX_DISCOVERY_URLS,
                )

            # ── 6. Build final crawl queue ─────────────────────────────────
            # Fresh url_dedup — guessed URLs are NOT pre-seeded here,
            # so all osm_with_site entries (including guessed ones) are queued.
            url_dedup = Deduplicator()
            # Pre-seed with known websites to avoid re-crawling existing leads
            for site in existing_websites:
                url_dedup.add(site)
            to_crawl: list[tuple[str, Optional[dict]]] = []

            for entity in osm_with_site + wd_with_site:
                url = entity["website"]
                if is_valid_url(url) and url_dedup.is_new(url):
                    url_dedup.add(url)
                    to_crawl.append((url, entity))

            for item in web_urls:
                url = item["url"]
                if is_valid_url(url) and url_dedup.is_new(url):
                    url_dedup.add(url)
                    to_crawl.append((url, None))

            logger.info(f"Job {job_id}: {len(to_crawl)} URLs to crawl")

            # ── 7. Parallel crawl in batches of 50 ────────────────────────
            semaphore = asyncio.Semaphore(settings.MAX_CONCURRENT_CRAWLS)
            batch_size = 50

            for batch_start in range(0, len(to_crawl), batch_size):
                if not await _pause_checkpoint(job_id):
                    return

                batch = to_crawl[batch_start: batch_start + batch_size]
                tasks = [
                    _crawl_and_save(job_id, url, prefill, intent.entity_type, semaphore)
                    for url, prefill in batch
                ]
                await asyncio.gather(*tasks, return_exceptions=True)

                _, partial = await crud.get_leads(db, job_id=job_id, page=1, page_size=1)
                await crud.update_job_status(db, job_id, "running", result_count=partial)
                await db.commit()
                logger.info(
                    f"Job {job_id}: crawl batch {batch_start // batch_size + 1} done "
                    f"— {partial} leads so far"
                )

            # ── 8. Finalize ────────────────────────────────────────────────
            _, total = await crud.get_leads(db, job_id=job_id, page=1, page_size=1)
            await crud.update_job_status(db, job_id, "done", result_count=total)
            await db.commit()
            logger.info(f"Job {job_id} done: {total} leads")

        except Exception as exc:
            logger.error(f"Job {job_id} failed: {exc}", exc_info=True)
            try:
                await db.rollback()
                await crud.update_job_status(db, job_id, "failed", error=str(exc)[:500])
                await db.commit()
            except Exception as inner:
                logger.error(f"Could not mark job {job_id} as failed: {inner}")

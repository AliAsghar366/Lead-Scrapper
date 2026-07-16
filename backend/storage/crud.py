"""Database operations (CRUD)."""
import json
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import select, update, func, delete, or_
from sqlalchemy.ext.asyncio import AsyncSession

from storage.models import (
    SearchJob, DiscoveredUrl, Lead,
    LeadNote, LeadTag, LeadList, LeadListMember,
    SavedSearch, ActivityLog,
)


def _now():
    return datetime.now(timezone.utc)


# ── Lead scoring ──────────────────────────────────────────────────────────────

def compute_score(lead: Lead) -> int:
    score = 0
    if lead.email:    score += 30
    if lead.phone:    score += 25
    if lead.website:  score += 20
    if lead.address:  score += 10
    if any([lead.facebook, lead.instagram, lead.linkedin, lead.twitter, lead.youtube]):
        score += 10
    if lead.email_verified is True: score += 5
    return min(score, 100)


# ── Jobs ──────────────────────────────────────────────────────────────────────

async def create_job(db: AsyncSession, query: str, entity_type: str, location: str, keywords: list) -> SearchJob:
    job = SearchJob(query=query, entity_type=entity_type, location=location,
                    keywords=json.dumps(keywords), status="pending")
    db.add(job)
    await db.flush()
    return job


async def get_job(db: AsyncSession, job_id: int) -> Optional[SearchJob]:
    result = await db.execute(select(SearchJob).where(SearchJob.id == job_id))
    return result.scalar_one_or_none()


async def list_jobs(db: AsyncSession, limit: int = 20) -> List[SearchJob]:
    result = await db.execute(select(SearchJob).order_by(SearchJob.created_at.desc()).limit(limit))
    return list(result.scalars().all())


async def update_job_status(db: AsyncSession, job_id: int, status: str,
                             result_count: int = 0, error: Optional[str] = None):
    await db.execute(
        update(SearchJob).where(SearchJob.id == job_id).values(
            status=status, result_count=result_count, error_message=error,
            completed_at=_now() if status in ("done", "failed") else None,
        )
    )


async def pause_job(db: AsyncSession, job_id: int):
    await db.execute(
        update(SearchJob).where(
            SearchJob.id == job_id, SearchJob.status == "running"
        ).values(status="paused")
    )
    await db.commit()


async def resume_job(db: AsyncSession, job_id: int):
    await db.execute(
        update(SearchJob).where(
            SearchJob.id == job_id, SearchJob.status == "paused"
        ).values(status="running")
    )
    await db.commit()


async def delete_job(db: AsyncSession, job_id: int):
    """Delete a job and all its leads (cascade)."""
    await db.execute(delete(Lead).where(Lead.job_id == job_id))
    await db.execute(delete(SearchJob).where(SearchJob.id == job_id))
    await db.commit()


async def delete_all_jobs(db: AsyncSession):
    """Wipe every job and every lead from the database."""
    await db.execute(delete(Lead))
    await db.execute(delete(SearchJob))
    await db.commit()


async def get_existing_names_websites(db: AsyncSession) -> tuple[set[str], set[str]]:
    """Return all known lead names and website URLs for cross-job deduplication."""
    from sqlalchemy import text
    names_r = await db.execute(select(Lead.name).where(Lead.name.isnot(None)))
    sites_r = await db.execute(select(Lead.website).where(Lead.website.isnot(None)))
    names = {r.lower().strip() for r in names_r.scalars().all() if r}
    sites = {r for r in sites_r.scalars().all() if r}
    return names, sites


# ── Discovered URLs ───────────────────────────────────────────────────────────

async def bulk_insert_urls(db: AsyncSession, job_id: int, urls: List[dict]):
    objs = [DiscoveredUrl(job_id=job_id, url=u["url"], domain=u["domain"],
                          source=u.get("source", "")) for u in urls]
    db.add_all(objs)
    await db.flush()


async def get_uncrawled_urls(db: AsyncSession, job_id: int) -> List[DiscoveredUrl]:
    result = await db.execute(
        select(DiscoveredUrl).where(DiscoveredUrl.job_id == job_id,
                                    DiscoveredUrl.crawled == False)  # noqa: E712
    )
    return list(result.scalars().all())


async def mark_url_crawled(db: AsyncSession, url_id: int):
    await db.execute(update(DiscoveredUrl).where(DiscoveredUrl.id == url_id).values(crawled=True))


# ── Leads ─────────────────────────────────────────────────────────────────────

async def insert_lead(db: AsyncSession, lead_data: dict) -> Lead:
    lead = Lead(**lead_data)
    lead.score = compute_score(lead)
    db.add(lead)
    await db.flush()
    return lead


async def get_lead(db: AsyncSession, lead_id: int) -> Optional[Lead]:
    result = await db.execute(select(Lead).where(Lead.id == lead_id))
    return result.scalar_one_or_none()


async def update_lead_status(db: AsyncSession, lead_id: int, status: str) -> Optional[Lead]:
    await db.execute(update(Lead).where(Lead.id == lead_id).values(
        status=status, updated_at=_now()
    ))
    await db.flush()
    return await get_lead(db, lead_id)


async def update_lead_fields(db: AsyncSession, lead_id: int, fields: dict) -> Optional[Lead]:
    fields["updated_at"] = _now()
    await db.execute(update(Lead).where(Lead.id == lead_id).values(**fields))
    await db.flush()
    lead = await get_lead(db, lead_id)
    if lead:
        new_score = compute_score(lead)
        await db.execute(update(Lead).where(Lead.id == lead_id).values(score=new_score))
        await db.flush()
        lead = await get_lead(db, lead_id)
    return lead


def _apply_lead_filters(q, job_id, has_phone, has_email, has_website,
                         has_address, has_social, status=None,
                         min_score=None, max_score=None,
                         tags=None, list_id=None, search=None):
    if job_id is not None:
        q = q.where(Lead.job_id == job_id)
    if has_phone:   q = q.where(Lead.phone.isnot(None))
    if has_email:   q = q.where(Lead.email.isnot(None))
    if has_website: q = q.where(Lead.website.isnot(None))
    if has_address: q = q.where(Lead.address.isnot(None))
    if has_social:
        q = q.where(or_(Lead.facebook.isnot(None), Lead.instagram.isnot(None),
                        Lead.linkedin.isnot(None), Lead.twitter.isnot(None),
                        Lead.youtube.isnot(None)))
    if status:
        q = q.where(Lead.status == status)
    if min_score is not None:
        q = q.where(Lead.score >= min_score)
    if max_score is not None:
        q = q.where(Lead.score <= max_score)
    if search:
        pat = f"%{search}%"
        q = q.where(or_(
            Lead.name.ilike(pat), Lead.email.ilike(pat),
            Lead.website.ilike(pat), Lead.address.ilike(pat),
            Lead.category.ilike(pat),
        ))
    if tags:
        for tag in tags:
            sub = select(LeadTag.lead_id).where(LeadTag.tag == tag)
            q = q.where(Lead.id.in_(sub))
    if list_id is not None:
        sub = select(LeadListMember.lead_id).where(LeadListMember.list_id == list_id)
        q = q.where(Lead.id.in_(sub))
    return q


async def get_leads(
    db: AsyncSession,
    job_id: Optional[int] = None,
    page: int = 1,
    page_size: int = 50,
    has_phone: bool = False,
    has_email: bool = False,
    has_website: bool = False,
    has_address: bool = False,
    has_social: bool = False,
    status: Optional[str] = None,
    min_score: Optional[int] = None,
    max_score: Optional[int] = None,
    tags: Optional[List[str]] = None,
    list_id: Optional[int] = None,
    search: Optional[str] = None,
    sort_by: str = "created_at",
    sort_dir: str = "desc",
) -> tuple[List[Lead], int]:
    q = select(Lead)
    count_q = select(func.count()).select_from(Lead)

    kw = dict(job_id=job_id, has_phone=has_phone, has_email=has_email,
              has_website=has_website, has_address=has_address, has_social=has_social,
              status=status, min_score=min_score, max_score=max_score,
              tags=tags, list_id=list_id, search=search)
    q = _apply_lead_filters(q, **kw)
    count_q = _apply_lead_filters(count_q, **kw)

    sort_col = getattr(Lead, sort_by, Lead.created_at)
    q = q.order_by(sort_col.desc() if sort_dir == "desc" else sort_col.asc())

    total = (await db.execute(count_q)).scalar_one()
    offset = (page - 1) * page_size
    items = list((await db.execute(q.offset(offset).limit(page_size))).scalars().all())
    return items, total


async def get_all_leads_for_job(db: AsyncSession, job_id: int, **filters) -> List[Lead]:
    q = select(Lead)
    q = _apply_lead_filters(q, job_id=job_id, **{k: filters.get(k, False)
        for k in ("has_phone","has_email","has_website","has_address","has_social")})
    result = await db.execute(q)
    return list(result.scalars().all())


async def bulk_update_leads(db: AsyncSession, lead_ids: List[int], fields: dict):
    fields["updated_at"] = _now()
    await db.execute(update(Lead).where(Lead.id.in_(lead_ids)).values(**fields))
    await db.flush()


async def delete_leads(db: AsyncSession, lead_ids: List[int]):
    await db.execute(delete(Lead).where(Lead.id.in_(lead_ids)))
    await db.flush()


# ── Notes ─────────────────────────────────────────────────────────────────────

async def add_note(db: AsyncSession, lead_id: int, content: str) -> LeadNote:
    note = LeadNote(lead_id=lead_id, content=content)
    db.add(note)
    await db.flush()
    await _log(db, lead_id, "note_added", content[:80])
    return note


async def get_notes(db: AsyncSession, lead_id: int) -> List[LeadNote]:
    result = await db.execute(
        select(LeadNote).where(LeadNote.lead_id == lead_id).order_by(LeadNote.created_at.desc())
    )
    return list(result.scalars().all())


async def delete_note(db: AsyncSession, note_id: int):
    await db.execute(delete(LeadNote).where(LeadNote.id == note_id))
    await db.flush()


# ── Tags ──────────────────────────────────────────────────────────────────────

async def add_tag(db: AsyncSession, lead_id: int, tag: str) -> LeadTag:
    existing = await db.execute(
        select(LeadTag).where(LeadTag.lead_id == lead_id, LeadTag.tag == tag.lower().strip())
    )
    if existing.scalar_one_or_none():
        return existing.scalar_one_or_none()  # type: ignore
    t = LeadTag(lead_id=lead_id, tag=tag.lower().strip())
    db.add(t)
    await db.flush()
    await _log(db, lead_id, "tagged", tag)
    return t


async def get_tags(db: AsyncSession, lead_id: int) -> List[str]:
    result = await db.execute(select(LeadTag.tag).where(LeadTag.lead_id == lead_id))
    return [r for r in result.scalars().all()]


async def remove_tag(db: AsyncSession, lead_id: int, tag: str):
    await db.execute(
        delete(LeadTag).where(LeadTag.lead_id == lead_id, LeadTag.tag == tag.lower().strip())
    )
    await db.flush()


async def get_all_tags(db: AsyncSession) -> List[str]:
    result = await db.execute(select(LeadTag.tag).distinct())
    return sorted(result.scalars().all())


# ── Lead Lists ────────────────────────────────────────────────────────────────

async def create_list(db: AsyncSession, name: str, description: str = "", color: str = "#3b82f6") -> LeadList:
    lst = LeadList(name=name, description=description, color=color)
    db.add(lst)
    await db.flush()
    return lst


async def get_lists(db: AsyncSession) -> List[LeadList]:
    result = await db.execute(select(LeadList).order_by(LeadList.created_at.desc()))
    return list(result.scalars().all())


async def get_list(db: AsyncSession, list_id: int) -> Optional[LeadList]:
    result = await db.execute(select(LeadList).where(LeadList.id == list_id))
    return result.scalar_one_or_none()


async def update_list(db: AsyncSession, list_id: int, **fields) -> Optional[LeadList]:
    await db.execute(update(LeadList).where(LeadList.id == list_id).values(**fields))
    await db.flush()
    return await get_list(db, list_id)


async def delete_list(db: AsyncSession, list_id: int):
    await db.execute(delete(LeadList).where(LeadList.id == list_id))
    await db.flush()


async def add_to_list(db: AsyncSession, list_id: int, lead_ids: List[int]):
    for lead_id in lead_ids:
        existing = await db.execute(
            select(LeadListMember).where(
                LeadListMember.list_id == list_id, LeadListMember.lead_id == lead_id
            )
        )
        if not existing.scalar_one_or_none():
            db.add(LeadListMember(list_id=list_id, lead_id=lead_id))
    await db.flush()


async def remove_from_list(db: AsyncSession, list_id: int, lead_id: int):
    await db.execute(
        delete(LeadListMember).where(
            LeadListMember.list_id == list_id, LeadListMember.lead_id == lead_id
        )
    )
    await db.flush()


async def get_list_member_count(db: AsyncSession, list_id: int) -> int:
    result = await db.execute(
        select(func.count()).select_from(LeadListMember).where(LeadListMember.list_id == list_id)
    )
    return result.scalar_one()


# ── Saved Searches ────────────────────────────────────────────────────────────

async def create_saved_search(db: AsyncSession, name: str, query: str) -> SavedSearch:
    ss = SavedSearch(name=name, query=query)
    db.add(ss)
    await db.flush()
    return ss


async def get_saved_searches(db: AsyncSession) -> List[SavedSearch]:
    result = await db.execute(select(SavedSearch).order_by(SavedSearch.created_at.desc()))
    return list(result.scalars().all())


async def update_saved_search(db: AsyncSession, ss_id: int, **fields):
    await db.execute(update(SavedSearch).where(SavedSearch.id == ss_id).values(**fields))
    await db.flush()


async def delete_saved_search(db: AsyncSession, ss_id: int):
    await db.execute(delete(SavedSearch).where(SavedSearch.id == ss_id))
    await db.flush()


# ── Activity Log ──────────────────────────────────────────────────────────────

async def _log(db: AsyncSession, lead_id: int, action: str, detail: str = ""):
    db.add(ActivityLog(lead_id=lead_id, action=action, detail=detail))
    await db.flush()


async def get_activity(db: AsyncSession, lead_id: int) -> List[ActivityLog]:
    result = await db.execute(
        select(ActivityLog).where(ActivityLog.lead_id == lead_id)
        .order_by(ActivityLog.created_at.desc()).limit(50)
    )
    return list(result.scalars().all())


# ── Email verification (DNS MX check) ────────────────────────────────────────

async def verify_email(db: AsyncSession, lead_id: int, email: str) -> bool:
    import asyncio
    domain = email.split("@")[-1] if "@" in email else ""
    verified = False
    if domain:
        try:
            loop = asyncio.get_event_loop()
            import dns.resolver
            records = await loop.run_in_executor(None, lambda: dns.resolver.resolve(domain, "MX"))
            verified = len(records) > 0
        except Exception:
            verified = False
    await db.execute(update(Lead).where(Lead.id == lead_id).values(
        email_verified=verified, updated_at=_now()
    ))
    await db.flush()
    # Recompute score
    lead = await get_lead(db, lead_id)
    if lead:
        await db.execute(update(Lead).where(Lead.id == lead_id).values(score=compute_score(lead)))
        await db.flush()
    await _log(db, lead_id, "email_verified", f"{'valid' if verified else 'invalid'} ({email})")
    return verified

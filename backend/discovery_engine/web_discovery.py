"""
Website Discovery Engine.

Since major search engines (Google, Bing, DDG) block automated access,
this engine supplements OSM data by:
  1. Generating smart URL guesses for businesses (businessname.com, .org, etc.)
  2. Using the DuckDuckGo Instant Answer API (returns curated links without scraping)

The primary data source is OSM/Overpass — use web discovery as enrichment only.
"""
import asyncio
import re
from urllib.parse import quote_plus

import httpx
from loguru import logger

from core.config import settings
from discovery_engine.deduplicator import extract_domain, is_valid_url

_HEADERS = {
    "User-Agent": settings.nominatim_user_agent,
    "Accept": "application/json",
    "Accept-Language": "en-US,en;q=0.9",
}

_NOISE_DOMAINS = {
    "google.com", "bing.com", "yahoo.com", "youtube.com",
    "facebook.com", "instagram.com", "twitter.com", "x.com",
    "wikipedia.org", "wikimedia.org", "amazon.com",
    "tripadvisor.com", "yelp.com", "zomato.com", "foursquare.com",
}


def _is_business_url(url: str) -> bool:
    domain = extract_domain(url)
    return is_valid_url(url) and not any(
        domain == nd or domain.endswith("." + nd) for nd in _NOISE_DOMAINS
    )


async def _ddg_instant(query: str) -> list[str]:
    """
    Use DuckDuckGo's free Instant Answer API.
    Returns only the curated top URLs from DuckDuckGo topics — no scraping.
    """
    url = "https://api.duckduckgo.com/"
    params = {
        "q": query,
        "format": "json",
        "no_html": "1",
        "no_redirect": "1",
        "skip_disambig": "1",
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url, params=params, headers=_HEADERS, follow_redirects=True)
            if resp.status_code != 200:
                return []
            data = resp.json()

        urls: list[str] = []
        # AbstractURL (Wikipedia etc.)
        if data.get("AbstractURL") and _is_business_url(data["AbstractURL"]):
            urls.append(data["AbstractURL"])
        # Official site from Infobox
        for item in data.get("Infobox", {}).get("content", []):
            if item.get("label", "").lower() in ("website", "official website"):
                val = item.get("value", "")
                if val and _is_business_url(val):
                    urls.append(val)
        # Related topics — each may have a link
        for topic in data.get("RelatedTopics", []):
            if isinstance(topic, dict):
                first_url = topic.get("FirstURL", "")
                if first_url and _is_business_url(first_url):
                    urls.append(first_url)

        return urls
    except Exception as exc:
        logger.debug(f"DDG instant API error for {query!r}: {exc}")
        return []


async def _guess_urls(business_name: str, location: str) -> list[str]:
    """
    Generate and verify URL guesses for a business name.
    e.g. "Bundu Khan" → ["https://bundukhan.com", "https://bundukhan.pk", ...]
    """
    slug = re.sub(r"[^a-z0-9]", "", business_name.lower().replace(" ", ""))
    if not slug or len(slug) < 3:
        return []
    # Determine country TLD from location
    country_tld = _country_tld(location)
    candidates = [
        f"https://www.{slug}.com",
        f"https://{slug}.com",
    ]
    if country_tld:
        candidates += [f"https://www.{slug}.{country_tld}", f"https://{slug}.{country_tld}"]
    candidates.append(f"https://www.{slug}.org")

    found: list[str] = []
    async with httpx.AsyncClient(timeout=8) as client:
        for url in candidates:
            try:
                resp = await client.get(url, follow_redirects=True,
                                        headers={"User-Agent": settings.nominatim_user_agent})
                if resp.status_code in (200, 301, 302, 307, 308):
                    final = str(resp.url)
                    if _is_business_url(final):
                        found.append(final)
                        break
            except Exception:
                pass
    return found


def _country_tld(location: str) -> str:
    """Map location keywords to country TLDs for URL guessing."""
    loc = location.lower()
    mapping = {
        "pakistan": "pk", "lahore": "pk", "karachi": "pk", "islamabad": "pk",
        "india": "in", "mumbai": "in", "delhi": "in", "bangalore": "in",
        "uk": "co.uk", "united kingdom": "co.uk", "london": "co.uk",
        "australia": "com.au", "sydney": "com.au", "melbourne": "com.au",
        "canada": "ca", "toronto": "ca", "vancouver": "ca",
        "germany": "de", "berlin": "de", "munich": "de",
        "france": "fr", "paris": "fr",
        "uae": "ae", "dubai": "ae", "abu dhabi": "ae",
    }
    for keyword, tld in mapping.items():
        if keyword in loc:
            return tld
    return ""


class WebDiscoveryEngine:
    async def discover(self, search_queries: list[str], max_urls: int = 30) -> list[dict]:
        """
        Discover business website URLs.
        Uses DuckDuckGo Instant Answer API (free, no key, no scraping).
        """
        results: list[dict] = []
        seen_domains: set[str] = set()

        for query in search_queries[:2]:  # limit to 2 queries to avoid rate limits
            if len(results) >= max_urls:
                break
            urls = await _ddg_instant(query)
            for url in urls:
                domain = extract_domain(url)
                if domain not in seen_domains and _is_business_url(url):
                    seen_domains.add(domain)
                    results.append({"url": url, "domain": domain, "source": "ddg_instant"})
            await asyncio.sleep(1.0)

        logger.info(f"Web discovery found {len(results)} URLs (via DDG Instant API)")
        return results[:max_urls]

    async def enrich_with_website(self, business_name: str, location: str) -> str | None:
        """Try to find a website for a named business via URL guessing."""
        urls = await _guess_urls(business_name, location)
        return urls[0] if urls else None


web_discovery = WebDiscoveryEngine()

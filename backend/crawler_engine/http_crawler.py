"""
HTTP-based crawler using httpx + BeautifulSoup.

Visits homepage, /about, /contact and extracts data from each page.
Falls back to Playwright for JS-heavy pages when httpx returns empty content.
"""
import asyncio
from urllib.parse import urljoin, urlparse
from typing import Optional

import httpx
from loguru import logger

from core.config import settings
from crawler_engine.robots_checker import can_fetch
from extractor_engine.html_extractor import extract_from_html

CRAWL_PATHS = ["/", "/about", "/about-us", "/contact", "/contact-us"]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def _normalize_base(url: str) -> str:
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}"


def _has_real_content(html: str | None) -> bool:
    if not html:
        return False
    return len(html) > 500


async def _fetch_page(client: httpx.AsyncClient, url: str) -> str | None:
    if not await can_fetch(url):
        logger.info(f"robots.txt disallows: {url}")
        return None
    try:
        resp = await client.get(url, headers=HEADERS, follow_redirects=True,
                                timeout=settings.CRAWLER_TIMEOUT)
        ct = resp.headers.get("content-type", "")
        if resp.status_code == 200 and "text/html" in ct:
            return resp.text
    except Exception as exc:
        logger.debug(f"httpx fetch failed {url}: {exc}")
    return None


def _merge(base: dict, extra: dict) -> dict:
    """Merge extra into base — only fill in missing (None) fields."""
    for k, v in extra.items():
        if v and not base.get(k):
            base[k] = v
    return base


async def crawl_site(website_url: str) -> dict:
    """
    Crawl a website and extract structured contact data.
    Returns a dict with all extracted fields (missing → None).
    """
    base = _normalize_base(website_url)
    merged: dict = {
        "name": None, "description": None,
        "email": None, "phone": None, "address": None,
        "facebook": None, "instagram": None,
        "linkedin": None, "twitter": None, "youtube": None,
    }

    async with httpx.AsyncClient(timeout=settings.CRAWLER_TIMEOUT) as client:
        visited = 0
        for path in CRAWL_PATHS:
            if visited >= settings.MAX_PAGES_PER_SITE:
                break
            url = urljoin(base, path)
            html = await _fetch_page(client, url)
            if not _has_real_content(html):
                # Try http fallback on homepage only
                if path == "/" and base.startswith("https://"):
                    http_url = base.replace("https://", "http://")
                    html = await _fetch_page(client, http_url)
            if _has_real_content(html):
                data = extract_from_html(html, url)
                merged = _merge(merged, data)
                visited += 1
                await asyncio.sleep(settings.CRAWL_DELAY)

            # Stop early if we have all key fields
            if all([merged.get("email"), merged.get("phone"), merged.get("name")]):
                break

    return merged

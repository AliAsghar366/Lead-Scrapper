"""robots.txt compliance checker with per-domain async locks and in-memory cache."""
import asyncio
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import httpx
from loguru import logger

from core.config import settings

_cache: dict[str, RobotFileParser | None] = {}
_domain_locks: dict[str, asyncio.Lock] = {}
_meta_lock = asyncio.Lock()   # only guards creation of per-domain locks


async def _get_domain_lock(domain: str) -> asyncio.Lock:
    async with _meta_lock:
        if domain not in _domain_locks:
            _domain_locks[domain] = asyncio.Lock()
    return _domain_locks[domain]


async def _fetch_robots(base_url: str) -> RobotFileParser | None:
    robots_url = urljoin(base_url, "/robots.txt")
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(
                robots_url,
                headers={"User-Agent": settings.USER_AGENT},
                follow_redirects=True,
            )
        if resp.status_code == 200:
            rp = RobotFileParser()
            rp.parse(resp.text.splitlines())
            return rp
    except Exception as exc:
        logger.debug(f"robots.txt fetch failed for {base_url}: {exc}")
    return None


async def can_fetch(url: str) -> bool:
    """Return True if allowed to crawl this URL per robots.txt."""
    if not settings.RESPECT_ROBOTS_TXT:
        return True
    parsed = urlparse(url)
    base = f"{parsed.scheme}://{parsed.netloc}"

    # Fast path: already cached (no lock needed for read)
    if base in _cache:
        rp = _cache[base]
        return rp is None or rp.can_fetch("*", url)

    # Slow path: fetch robots.txt under a per-domain lock
    domain_lock = await _get_domain_lock(base)
    async with domain_lock:
        if base not in _cache:           # double-check after acquiring lock
            _cache[base] = await _fetch_robots(base)

    rp = _cache.get(base)
    return rp is None or rp.can_fetch("*", url)

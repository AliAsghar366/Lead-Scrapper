"""
LinkedIn enrichment via search engine snippets.

Searches Google/Bing for "site:linkedin.com/company [name]" and extracts
company info (industry, employee count, description) from the result snippets.
Never hits LinkedIn directly — reads only publicly indexed search results.
"""
import re
import httpx
from loguru import logger
from core.config import settings

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}

_EMPLOYEE_PATTERNS = [
    r"(\d[\d,]+)\s*(?:employees|employee|staff|workers|team members)",
    r"Company size[:\s]+(\d[\d,\-\+\s]+(?:employees)?)",
    r"(\d+[-–]\d+)\s*employees",
    r"(\d+\+)\s*employees",
]

_INDUSTRY_PATTERNS = [
    r"Industry[:\s]+([A-Za-z &/\-,]+?)(?:\s*·|\s*\||$)",
    r"(?:Sector|Field)[:\s]+([A-Za-z &/\-,]+?)(?:\s*·|\s*\||$)",
]

_FOUNDED_PATTERNS = [
    r"Founded[:\s]+(\d{4})",
    r"Established[:\s]+(\d{4})",
    r"Since (\d{4})",
]


async def enrich_from_search(name: str, location: str = "") -> dict:
    """Return a partial Lead field dict with LinkedIn-derived data."""
    query = f'site:linkedin.com/company "{name}"'
    if location:
        query += f" {location}"

    snippet = await _bing_snippet(query) or await _ddg_snippet(query)
    if not snippet:
        logger.debug(f"LinkedIn enricher: no snippet for {name!r}")
        return {}

    updates: dict = {}

    for pat in _EMPLOYEE_PATTERNS:
        m = re.search(pat, snippet, re.IGNORECASE)
        if m:
            updates["employee_count"] = m.group(1).replace(",", "").strip()
            break

    for pat in _INDUSTRY_PATTERNS:
        m = re.search(pat, snippet, re.IGNORECASE)
        if m:
            updates["industry"] = m.group(1).strip()
            break

    for pat in _FOUNDED_PATTERNS:
        m = re.search(pat, snippet, re.IGNORECASE)
        if m:
            updates["founded_year"] = m.group(1).strip()
            break

    # Extract LinkedIn URL
    li_match = re.search(r"https?://(?:www\.)?linkedin\.com/company/[^\s\"'<>]+", snippet)
    if li_match:
        updates["linkedin"] = li_match.group(0).rstrip("/.,")

    logger.debug(f"LinkedIn enricher: {name!r} → {updates}")
    return updates


async def _bing_snippet(query: str) -> str | None:
    try:
        async with httpx.AsyncClient(timeout=10, headers=_HEADERS) as client:
            resp = await client.get(
                "https://www.bing.com/search",
                params={"q": query, "count": "3"},
            )
            resp.raise_for_status()
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(resp.text, "lxml")
        parts = []
        for result in soup.select(".b_algo")[:3]:
            caption = result.select_one(".b_caption p")
            title = result.select_one("h2")
            if title:
                parts.append(title.get_text(" ", strip=True))
            if caption:
                parts.append(caption.get_text(" ", strip=True))
        return " | ".join(parts) if parts else None
    except Exception as exc:
        logger.debug(f"Bing snippet failed: {exc}")
        return None


async def _ddg_snippet(query: str) -> str | None:
    try:
        async with httpx.AsyncClient(timeout=10, headers=_HEADERS) as client:
            resp = await client.get(
                "https://html.duckduckgo.com/html/",
                params={"q": query},
            )
            resp.raise_for_status()
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(resp.text, "lxml")
        parts = []
        for result in soup.select(".result")[:3]:
            snippet = result.select_one(".result__snippet")
            title = result.select_one(".result__title")
            if title:
                parts.append(title.get_text(" ", strip=True))
            if snippet:
                parts.append(snippet.get_text(" ", strip=True))
        return " | ".join(parts) if parts else None
    except Exception as exc:
        logger.debug(f"DDG snippet failed: {exc}")
        return None

"""
HTML Extractor Engine.

Extracts structured data from raw HTML.
Follows strict "only extract what is present" policy — no inference.
"""
import json
import re
from typing import Optional
from bs4 import BeautifulSoup
from loguru import logger

from extractor_engine.patterns import EMAIL, PHONE, SOCIAL, JUNK_EMAILS, JUNK_PHONES


def _clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _is_valid_email(email: str) -> bool:
    em = email.lower()
    return not any(j in em for j in JUNK_EMAILS) and len(em) < 200


def _is_valid_phone(phone: str) -> bool:
    digits = re.sub(r"\D", "", phone)
    return 7 <= len(digits) <= 15 and digits not in JUNK_PHONES


def _extract_jsonld(soup: BeautifulSoup) -> dict:
    """Extract structured data from JSON-LD script tags."""
    result = {}
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
            if isinstance(data, list):
                data = data[0]
            if isinstance(data, dict):
                result["name"] = result.get("name") or data.get("name")
                result["description"] = result.get("description") or data.get("description")
                result["email"] = result.get("email") or data.get("email")
                result["phone"] = result.get("phone") or data.get("telephone")
                addr = data.get("address", {})
                if isinstance(addr, dict):
                    parts = [
                        addr.get("streetAddress", ""),
                        addr.get("addressLocality", ""),
                        addr.get("addressRegion", ""),
                        addr.get("addressCountry", ""),
                    ]
                    result["address"] = result.get("address") or ", ".join(p for p in parts if p)
                social = data.get("sameAs", [])
                if isinstance(social, str):
                    social = [social]
                for link in social:
                    for platform, pattern in SOCIAL.items():
                        if platform not in result and pattern.search(link):
                            result[platform] = link
        except Exception:
            pass
    return result


def _extract_meta(soup: BeautifulSoup) -> dict:
    result = {}
    for meta in soup.find_all("meta"):
        name = (meta.get("name") or meta.get("property") or "").lower()
        content = meta.get("content", "").strip()
        if not content:
            continue
        if name in ("description", "og:description"):
            result.setdefault("description", content)
        if name == "og:site_name":
            result.setdefault("name", content)
    return result


def extract_from_html(html: str, page_url: str = "") -> dict:
    """
    Extract all available contact data from an HTML page.
    Returns only what was explicitly found — missing fields are None.
    """
    soup = BeautifulSoup(html, "lxml")
    text = soup.get_text(" ", strip=True)

    result: dict = {
        "name": None,
        "description": None,
        "email": None,
        "phone": None,
        "address": None,
        "facebook": None,
        "instagram": None,
        "linkedin": None,
        "twitter": None,
        "youtube": None,
    }

    # 1. JSON-LD (most reliable structured data)
    jld = _extract_jsonld(soup)
    result.update({k: v for k, v in jld.items() if v})

    # 2. Meta tags
    meta = _extract_meta(soup)
    for k, v in meta.items():
        if v and not result.get(k):
            result[k] = v

    # 3. Page <title> as name fallback
    if not result["name"]:
        title_tag = soup.find("title")
        if title_tag:
            raw = title_tag.get_text(strip=True)
            # Strip common suffixes like "| Home" or "- Official Site"
            name = re.split(r"[|\-–—]", raw)[0].strip()
            if name:
                result["name"] = name

    # 4. Email extraction (mailto: links first, then regex)
    emails: set[str] = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.lower().startswith("mailto:"):
            email = href[7:].split("?")[0].strip().lower()
            if email and _is_valid_email(email):
                emails.add(email)
    for m in EMAIL.finditer(text):
        email = m.group(1).lower()
        if _is_valid_email(email):
            emails.add(email)
    if emails and not result["email"]:
        result["email"] = sorted(emails)[0]

    # 5. Phone extraction (tel: links first, then regex)
    phones: set[str] = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.lower().startswith("tel:"):
            phone = re.sub(r"[^\d+]", "", href[4:])
            if phone and _is_valid_phone(phone):
                phones.add(phone)
    for m in PHONE.finditer(text):
        phone = m.group(0).strip()
        if _is_valid_phone(phone):
            phones.add(phone)
    if phones and not result["phone"]:
        result["phone"] = sorted(phones, key=len, reverse=True)[0]

    # 6. Social links from <a> tags in full HTML
    html_str = str(soup)
    for platform, pattern in SOCIAL.items():
        if not result[platform]:
            m = pattern.search(html_str)
            if m:
                result[platform] = m.group(0).rstrip("/")

    # 7. Address: look for schema.org microdata or common patterns
    if not result["address"]:
        for tag in soup.find_all(itemprop="address"):
            addr = _clean_text(tag.get_text())
            if addr and len(addr) > 5:
                result["address"] = addr
                break

    # 8. Description fallback: first <p> with substantial text
    if not result["description"]:
        for p in soup.find_all("p"):
            txt = _clean_text(p.get_text())
            if 40 < len(txt) < 500:
                result["description"] = txt
                break

    return result

"""URL and domain deduplication utilities."""
import re
from urllib.parse import urlparse, urlunparse


# Domains to skip — these are directories/aggregators, not actual business sites
SKIP_DOMAINS = {
    "facebook.com", "instagram.com", "twitter.com", "x.com",
    "linkedin.com", "youtube.com", "tiktok.com",
    "wikipedia.org", "wikimedia.org",
    "google.com", "google.co", "bing.com", "yahoo.com", "duckduckgo.com",
    "yelp.com", "tripadvisor.com", "maps.google.com",
    "apple.com", "amazon.com", "ebay.com",
    "foursquare.com", "zomato.com", "opentable.com",
    "yellowpages.com", "whitepages.com",
    "trustpilot.com", "glassdoor.com",
}

_PARAM_STRIP_PATTERN = re.compile(r"[?#].*$")


def normalize_url(url: str) -> str:
    """Normalize a URL for deduplication."""
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    parsed = urlparse(url)
    netloc = parsed.netloc.lower().lstrip("www.")
    path = parsed.path.rstrip("/") or "/"
    return urlunparse(("https", netloc, path, "", "", ""))


def extract_domain(url: str) -> str:
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    parsed = urlparse(url)
    return parsed.netloc.lower().lstrip("www.")


def is_valid_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower().lstrip("www.")
        if not parsed.scheme or not domain:
            return False
        if domain in SKIP_DOMAINS:
            return False
        # Skip very short or clearly wrong URLs
        if len(domain) < 4 or "." not in domain:
            return False
        return True
    except Exception:
        return False


class Deduplicator:
    def __init__(self):
        self._seen_domains: set[str] = set()
        self._seen_urls: set[str] = set()
        self._seen_names: set[str] = set()

    def add_name(self, name: str):
        self._seen_names.add(name.lower().strip())

    def is_new_name(self, name: str) -> bool:
        return name.lower().strip() not in self._seen_names

    def is_new(self, url: str) -> bool:
        domain = extract_domain(url)
        if domain in self._seen_domains:
            return False
        norm = normalize_url(url)
        if norm in self._seen_urls:
            return False
        return True

    def add(self, url: str):
        domain = extract_domain(url)
        norm = normalize_url(url)
        self._seen_domains.add(domain)
        self._seen_urls.add(norm)

    def filter(self, urls: list[dict]) -> list[dict]:
        result = []
        for item in urls:
            url = item["url"]
            if is_valid_url(url) and self.is_new(url):
                self.add(url)
                result.append(item)
        return result

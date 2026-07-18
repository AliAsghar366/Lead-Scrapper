import os
from pydantic_settings import BaseSettings


def _default_db_url() -> str:
    # Use /data/ if it exists (Railway persistent volume), else local file
    if os.path.isdir("/data"):
        return "sqlite+aiosqlite:////data/leadcrawler.db"
    return "sqlite+aiosqlite:///./leadcrawler.db"


class Settings(BaseSettings):
    APP_NAME: str = "UniversalLeadCrawler"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    ENVIRONMENT: str = "production"

    # Database — SQLite by default, swap to PostgreSQL via DATABASE_URL env var
    DATABASE_URL: str = _default_db_url()

    # CORS — "*" allows any origin (Vercel, local dev, etc.)
    CORS_ORIGINS: str = "*"

    @property
    def cors_origins_list(self) -> list[str]:
        if self.CORS_ORIGINS.strip() == "*":
            return ["*"]
        return [o.strip() for o in self.CORS_ORIGINS.split(",")]

    # Crawler behaviour
    CRAWLER_TIMEOUT: int = 20           # seconds per page
    CRAWL_DELAY: float = 1.0            # seconds between pages of same domain
    MAX_PAGES_PER_SITE: int = 3         # homepage + contact + about
    MAX_CONCURRENT_CRAWLS: int = 5      # parallel domain crawls (low for free tier RAM)
    RESPECT_ROBOTS_TXT: bool = True

    # Discovery
    SEARCH_RESULTS_PER_QUERY: int = 10  # how many URLs to try per search query
    MAX_DISCOVERY_URLS: int = 200       # total cap per job

    # OSM
    OVERPASS_BASE_URL: str = "https://overpass-api.de/api/interpreter"
    NOMINATIM_BASE_URL: str = "https://nominatim.openstreetmap.org"
    # Nominatim requires a valid email in User-Agent: https://operations.osmfoundation.org/policies/nominatim/
    CONTACT_EMAIL: str = "leadcrawler@research.local"
    USER_AGENT: str = "UniversalLeadCrawler/1.0"

    @property
    def nominatim_user_agent(self) -> str:
        return f"{self.USER_AGENT} ({self.CONTACT_EMAIL})"

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()

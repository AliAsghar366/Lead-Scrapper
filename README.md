# Universal LeadCrawler AI

A production-grade entity intelligence crawler that discovers business data from the open web — **no paid APIs required**.

## How It Works

```
User Query → Query Engine → Discovery Engine → Crawler + Extractor → Database → Export
```

1. **Query Engine** parses `"restaurants in Lahore"` → `{ entity_type: "restaurant", location: "Lahore" }`
2. **Discovery Engine** finds relevant websites via:
   - OpenStreetMap / Overpass API (structured OSM data)
   - DuckDuckGo HTML scraping (no API key needed)
   - Bing fallback
3. **Crawler Engine** visits each site's `/`, `/about`, `/contact` pages
4. **Extractor Engine** pulls: name, email, phone, address, social links (Facebook, Instagram, LinkedIn, Twitter, YouTube)
5. Results stored in SQLite (PostgreSQL-ready) and exported to Excel/CSV

## Quick Start (Local)

### Backend

```bash
cd backend

# Create virtual environment
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate    # Linux/Mac

# Install dependencies
pip install -r requirements.txt

# Install Playwright browser (for JS-heavy sites)
playwright install chromium

# Copy env file
copy .env.example .env        # Windows
# cp .env.example .env        # Linux/Mac

# Start the API server
uvicorn main:app --reload --port 8000
```

API docs: http://localhost:8000/docs

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend: http://localhost:3000

### Docker (full stack)

```bash
cp .env.example .env
docker-compose up --build
```

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/search` | Submit a query |
| GET | `/api/v1/search/status/{job_id}` | Poll job status |
| GET | `/api/v1/search/history` | Recent searches |
| GET | `/api/v1/results?job_id={id}` | Get extracted leads |
| GET | `/api/v1/export/excel?job_id={id}` | Download Excel |
| GET | `/api/v1/export/csv?job_id={id}` | Download CSV |

### Example: Submit a search

```bash
curl -X POST http://localhost:8000/api/v1/search \
  -H "Content-Type: application/json" \
  -d '{"query": "restaurants in Lahore"}'
```

Response:
```json
{
  "job_id": 1,
  "message": "Search started",
  "entity_type": "restaurant",
  "location": "Lahore"
}
```

### Poll for completion

```bash
curl http://localhost:8000/api/v1/search/status/1
```

### Download results

```bash
curl http://localhost:8000/api/v1/export/excel?job_id=1 -o leads.xlsx
```

## Architecture

```
backend/
├── main.py                      # FastAPI app
├── core/
│   └── config.py                # Settings (env vars)
├── query_engine/
│   └── parser.py                # NL query → structured intent
├── discovery_engine/
│   ├── osm_discovery.py         # Overpass/Nominatim
│   ├── web_discovery.py         # DuckDuckGo + Bing scraping
│   └── deduplicator.py          # URL/domain dedup
├── crawler_engine/
│   ├── http_crawler.py          # httpx multi-page crawler
│   └── robots_checker.py        # robots.txt compliance
├── extractor_engine/
│   ├── html_extractor.py        # BeautifulSoup + JSON-LD
│   └── patterns.py              # Regex for email/phone/social
├── storage/
│   ├── database.py              # SQLAlchemy async engine
│   ├── models.py                # ORM models
│   └── crud.py                  # DB operations
├── workers/
│   └── job_runner.py            # Full pipeline orchestrator
└── api/routes/
    ├── search.py                # Search endpoints
    ├── results.py               # Results endpoints
    └── export.py                # CSV/Excel export

frontend/
└── src/
    ├── app/page.tsx             # Main page
    ├── components/
    │   ├── SearchBox.tsx        # Query input + examples
    │   ├── JobStatus.tsx        # Live job progress
    │   ├── ResultsTable.tsx     # Paginated results table
    │   └── HistorySidebar.tsx   # Recent searches
    ├── hooks/useJobPoller.ts    # Auto-polling hook
    ├── lib/api.ts               # Backend API client
    └── types/index.ts           # TypeScript interfaces
```

## Output Fields

| Field | Description |
|-------|-------------|
| Name | Business name (from JSON-LD, meta tags, or page title) |
| Website | Discovered or provided URL |
| Email | Extracted from mailto: links or page text |
| Phone | Extracted from tel: links or page text |
| Address | Extracted from schema.org or microdata |
| Facebook | Facebook page URL |
| Instagram | Instagram profile URL |
| LinkedIn | LinkedIn company URL |
| Twitter/X | Twitter/X profile URL |
| YouTube | YouTube channel URL |

**Missing values are always blank (never hallucinated).**

## Configuration (.env)

```env
DATABASE_URL=sqlite+aiosqlite:///./leadcrawler.db
CRAWLER_TIMEOUT=20
CRAWL_DELAY=1.5
MAX_PAGES_PER_SITE=5
MAX_CONCURRENT_CRAWLS=5
RESPECT_ROBOTS_TXT=true
MAX_DISCOVERY_URLS=30
```

## Switching to PostgreSQL

1. Uncomment `asyncpg` in `requirements.txt`
2. Set `DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/db`

## Legal & Ethical Notes

- Only publicly accessible data is crawled
- robots.txt is respected by default
- Rate limiting prevents aggressive crawling
- No login-gated or paywalled data is accessed

"""Universal LeadCrawler AI — FastAPI entry point."""
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from core.config import settings
from storage.database import init_db
from api.routes import search, results, export, leads


logger.remove()
logger.add(sys.stderr, level="DEBUG" if settings.DEBUG else "INFO", colorize=True,
           format="<green>{time:HH:mm:ss}</green> | <level>{level}</level> | {message}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    await init_db()
    logger.info("Database ready.")
    yield
    logger.info("Shutdown complete.")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Universal Entity Intelligence Crawler — discover and enrich business data from the open web.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(search.router,  prefix="/api/v1")
app.include_router(results.router, prefix="/api/v1")
app.include_router(export.router,  prefix="/api/v1")
app.include_router(leads.router,   prefix="/api/v1")


@app.get("/health")
async def health():
    return {"status": "ok", "version": settings.APP_VERSION}


@app.get("/")
async def root():
    return {"app": settings.APP_NAME, "docs": "/docs"}

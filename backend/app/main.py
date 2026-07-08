import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.collectors.scheduler import run_bootstrap_pipeline, start_background_tasks, stop_background_tasks
from app.config import settings
from app.db import init_db
from app.routers import api, v2, v3
from app.services.store import store

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s:%(name)s:%(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)
# Reduce noisy HTTP logs (may include tokens in URLs)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)


@asynccontextmanager
async def lifespan(_: FastAPI):
    t0 = time.monotonic()
    init_db()
    t1 = time.monotonic()
    logger.info("Startup: init_db took %.2fs", t1 - t0)
    store.bootstrap_from_db()
    t2 = time.monotonic()
    logger.info("Startup: bootstrap_from_db took %.2fs", t2 - t1)
    await run_bootstrap_pipeline()
    t3 = time.monotonic()
    logger.info("Startup: run_bootstrap_pipeline took %.2fs", t3 - t2)
    start_background_tasks()
    logger.info("HyperPulse Phase 2 pipeline ready (total startup %.2fs)", t3 - t0)
    yield
    await stop_background_tasks()


app = FastAPI(
    title="HyperPulse API",
    description="AI-powered intelligence platform for Hyperliquid traders",
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api.router)
app.include_router(v2.router)
app.include_router(v3.router)


@app.get("/health")
def health() -> dict[str, str | bool]:
    status = store.pipeline_status()
    return {
        "status": "ok",
        "phase": "2",
        "telegram_configured": status.telegram_configured,
        "ai_provider": status.ai_provider,
    }

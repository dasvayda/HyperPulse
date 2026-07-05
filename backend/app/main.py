import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.collectors.scheduler import run_bootstrap_pipeline, start_background_tasks, stop_background_tasks
from app.config import settings
from app.db import init_db
from app.routers import api, v2
from app.services.store import store

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    store.bootstrap_from_db()
    await run_bootstrap_pipeline()
    start_background_tasks()
    logger.info("HyperPulse Phase 2 pipeline ready")
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


@app.get("/health")
def health() -> dict[str, str | bool]:
    status = store.pipeline_status()
    return {
        "status": "ok",
        "phase": "2",
        "telegram_configured": status.telegram_configured,
        "ai_provider": status.ai_provider,
    }

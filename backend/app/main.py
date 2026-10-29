import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.collectors.scheduler import run_bootstrap_pipeline, start_background_tasks, stop_background_tasks
from app.config import settings
from app.db import init_db
from app.logging_config import configure_logging
from app.routers import api, v2, v3
from app.services.store import store
from app.services.readiness import get_readiness

configure_logging()
logger = logging.getLogger(__name__)


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
    logger.info("Pipeline initialized (%.2fs); API readiness requires a successful HTTP health check", t3 - t0)
    yield
    await stop_background_tasks()


def health() -> dict[str, str | bool]:
    status = store.pipeline_status()
    return {
        "status": "ok",
        "phase": "2",
        "telegram_configured": status.telegram_configured,
        "ai_provider": status.ai_provider,
    }


def readiness() -> JSONResponse:
    """Readiness for deploys: DB and fresh collector must be healthy.

    Redis fallback is reported separately and remains usable for the initial
    single-instance release, so it does not alone make the service unready.
    """

    result = get_readiness()
    return JSONResponse(
        status_code=200 if result.status == "ready" else 503,
        content=result.model_dump(mode="json"),
    )


def create_app() -> FastAPI:
    # Validate before serving, not on the first browser request.
    origins = settings.cors_origin_list
    application = FastAPI(
        title="HyperPulse API",
        description="AI-powered intelligence platform for Hyperliquid traders",
        version="0.2.0",
        lifespan=lifespan,
        docs_url="/docs" if settings.api_docs_enabled else None,
        redoc_url="/redoc" if settings.api_docs_enabled else None,
        openapi_url="/openapi.json" if settings.api_docs_enabled else None,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=settings.cors_allow_credentials,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "X-Pipeline-Token"],
    )
    application.include_router(api.router)
    application.include_router(v2.router)
    application.include_router(v3.router)
    application.add_api_route("/health", health, methods=["GET"])
    application.add_api_route("/health/ready", readiness, methods=["GET"])
    return application


app = create_app()

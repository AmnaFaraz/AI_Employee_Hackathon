"""
FastAPI Application — Customer Success Digital FTE

Main application entry point with lifespan management,
middleware configuration, and router registration.
"""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from dotenv import load_dotenv

load_dotenv(override=True)

from src.database.connection import init_db, close_db
# from src.workers.producer import get_producer, close_producer
from src.api.routers import channels, tickets, customers, monitoring

logger = logging.getLogger(__name__)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
)


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle management."""
    logger.info("Starting Customer Success Digital FTE API…")

    # Initialise database connection pool
    init_db()
    logger.info("Database pool initialised")

    # Initialise Kafka producer
    # try:
    #     await get_producer()
    #     logger.info("Kafka producer initialised")
    # except Exception as exc:
    #     logger.warning("Kafka producer failed to start (continuing): %s", exc)

    yield  # ← Application runs here

    logger.info("Shutting down…")
    # await close_producer()
    await close_db()
    logger.info("Shutdown complete")


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

def create_app() -> FastAPI:
    app = FastAPI(
        title="Customer Success Digital FTE",
        description=(
            "24/7 AI Customer Success Employee — handles support requests "
            "across Email, WhatsApp, and Web Support Form."
        ),
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # CORS (allow web form widget from any origin in dev; restrict in prod)
    allowed_origins = os.environ.get("CORS_ORIGINS", "*").split(",")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Trusted hosts (security hardening in production)
    trusted_hosts = os.environ.get("TRUSTED_HOSTS", "*").split(",")
    if trusted_hosts != ["*"]:
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=trusted_hosts)

    # Routers
    app.include_router(monitoring.router, tags=["Health & Monitoring"])
    app.include_router(channels.router, prefix="/api/v1/channels", tags=["Channel Intake"])
    app.include_router(tickets.router, prefix="/api/v1/tickets", tags=["Tickets"])
    app.include_router(customers.router, prefix="/api/v1/customers", tags=["Customers"])

    @app.exception_handler(Exception)
    async def global_exception_handler(request, exc):
        logger.error("Unhandled exception: %s", exc, exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error", "detail": str(exc)},
        )

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "src.api.main:app",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "8000")),
        reload=os.environ.get("ENV", "production") == "development",
        workers=int(os.environ.get("UVICORN_WORKERS", "1")),
        log_level="info",
    )

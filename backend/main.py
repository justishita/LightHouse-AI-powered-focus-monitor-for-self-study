"""
main.py — FastAPI application entry point.

Why this file stays thin: it only wires together middleware, routers, and
startup/shutdown events. All real logic lives in services/ so main.py
remains easy to scan and routers stay swappable without touching app setup.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from routers import detection, session as session_router
from services.detection_service import detection_service
from services.session_service import session_service
from utils.database import init_db
from utils.logger import get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: init DB schema (idempotent — safe to call every boot).
    # Models load lazily on session start, so boot stays fast.
    init_db()
    logger.info(f"{settings.APP_NAME} starting up in '{settings.APP_ENV}' mode")
    yield
    # Shutdown: stop any running session cleanly so the webcam is released
    # and final stats are persisted even on Ctrl-C / server restart.
    if session_service.is_active:
        logger.info("Server shutting down with an active session — stopping and saving stats")
        session_service.stop()
    elif detection_service.is_running:
        # detection started standalone (via /api/detection/start), not via a session
        detection_service.stop()
    logger.info("Shutdown complete")


app = FastAPI(title=settings.APP_NAME, lifespan=lifespan)

# CORS restricted to the Vite dev server origin via .env, not "*" — even
# in local dev we don't want arbitrary pages on the LAN reading session data.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "env": settings.APP_ENV,
        "session_active": session_service.is_active,
    }


app.include_router(detection.router, prefix="/api/detection", tags=["detection"])
app.include_router(session_router.router, prefix="/api/session", tags=["session"])

# Future routers:
# from routers import blocker
# app.include_router(blocker.router, prefix="/api/blocker", tags=["blocker"])

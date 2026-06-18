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
from routers import detection
from services.detection_service import detection_service
from utils.logger import get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: nothing to warm up — detection models load lazily inside
    # detection_service.start() so server boot stays fast even before a
    # session begins (no cost paid for a session that's never started).
    logger.info(f"{settings.APP_NAME} starting up in '{settings.APP_ENV}' mode")
    yield
    # Shutdown: make sure the webcam gets released even if the server is
    # killed mid-session — otherwise the camera can stay "in use" from the
    # OS's perspective until the process fully exits.
    if detection_service.is_running:
        logger.info("Server shutting down with an active session — stopping detection")
        detection_service.stop()
    logger.info("Shutdown complete")


app = FastAPI(title=settings.APP_NAME, lifespan=lifespan)

# CORS is restricted to the Vite dev server origin via .env, not "*" —
# even in local dev we don't want any arbitrary site on the LAN reading
# session/detection data if the backend port happens to be reachable.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(detection.router, prefix="/api/detection", tags=["detection"])


@app.get("/health")
async def health_check():
    # Cheap endpoint for the frontend (and you, manually via browser/curl)
    # to confirm the backend is reachable before wiring up anything more complex.
    return {"status": "ok", "app": settings.APP_NAME, "env": settings.APP_ENV}


# Additional routers (session, blocker) get included here as those
# sections are built, following the same pattern as detection above.

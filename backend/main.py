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
from utils.logger import get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: nothing to warm up yet at the skeleton stage — detection
    # models will load lazily inside the detection service once that
    # section exists, so server boot stays fast even before a session starts.
    logger.info(f"{settings.APP_NAME} starting up in '{settings.APP_ENV}' mode")
    yield
    # Shutdown: placeholder for releasing the camera/model resources once
    # those services exist — keeping the hook here now so we don't forget it.
    logger.info("Shutting down — releasing any held resources")


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


@app.get("/health")
async def health_check():
    # Cheap endpoint for the frontend (and you, manually via browser/curl)
    # to confirm the backend is reachable before wiring up anything more complex.
    return {"status": "ok", "app": settings.APP_NAME, "env": settings.APP_ENV}


# Routers get included here as each section is built, e.g.:
# from routers import session, detection, blocker
# app.include_router(session.router, prefix="/api/session", tags=["session"])

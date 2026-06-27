"""
routers/session.py — Session start/stop/stats/history endpoints.

All business logic lives in session_service — this file only validates
inputs, calls services, and shapes responses, per the project rule of
"routers just call services".

Endpoint summary:
  POST /api/session/start            Start a new session
  POST /api/session/stop             Stop the active session, persist stats
  GET  /api/session/live             Live stats for the current session
  GET  /api/session/history          All completed sessions (newest first)
  GET  /api/session/{id}             One session + its distraction events
"""

import asyncio

from fastapi import APIRouter, HTTPException

from models.schemas import (
    LiveStatsResponse,
    SessionDetailResponse,
    SessionHistoryItem,
    SessionStartResponse,
    SessionStopResponse,
)
from services.session_service import (
    get_session_detail,
    get_session_history,
    session_service,
)
from utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()


@router.post("/start", response_model=SessionStartResponse)
async def start_session():
    # session_service.start() calls detection_service.start() inside,
    # which opens the webcam and loads models — blocking I/O, so we
    # offload to a thread to avoid stalling the event loop.
    result = await asyncio.to_thread(session_service.start)
    return SessionStartResponse(**result)


@router.post("/stop", response_model=SessionStopResponse)
async def stop_session():
    result = await asyncio.to_thread(session_service.stop)
    return SessionStopResponse(**result)


@router.get("/live", response_model=LiveStatsResponse)
async def get_live_stats():
    stats = session_service.get_live_stats()
    if stats is None:
        # No session running — return an explicit inactive payload rather
        # than a 404, because the frontend will poll this endpoint and
        # needs a clean "nothing to show yet" state to render.
        return LiveStatsResponse(active=False)
    return LiveStatsResponse(active=True, **stats)


@router.get("/history", response_model=list[SessionHistoryItem])
async def get_history(limit: int = 50):
    rows = await asyncio.to_thread(get_session_history, limit)
    return [SessionHistoryItem(**r) for r in rows]


@router.get("/{session_id}", response_model=SessionDetailResponse)
async def get_session(session_id: int):
    detail = await asyncio.to_thread(get_session_detail, session_id)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    return SessionDetailResponse(**detail)

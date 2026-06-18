"""
routers/detection.py — Webcam detection endpoints.

Why start/stop live here rather than only inside session.py: this lets us
test detection completely standalone before the session router exists yet.
Once session.py is built, it will call detection_service.start()/stop()
directly (not hit these HTTP endpoints internally) — these stay as the
endpoints the frontend, or you manually via /docs, can use to test this
section in isolation.

No business logic lives in this file — it only validates input and calls
into detection_service, per the project's router/service split.
"""

import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from config import settings
from models.schemas import DetectionActionResponse, DetectionStatusResponse
from services.detection_service import detection_service
from utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()


@router.post("/start", response_model=DetectionActionResponse)
async def start_detection():
    if detection_service.is_running:
        return DetectionActionResponse(status="already_running")

    # Camera/model init touches blocking I/O (opening the webcam device,
    # loading model weights from disk) — running it via asyncio.to_thread
    # keeps this endpoint from blocking the event loop while that happens.
    started = await asyncio.to_thread(detection_service.start)
    if not started:
        return DetectionActionResponse(
            status="error",
            detail="Could not start detection — check that the webcam isn't in use by another app.",
        )
    return DetectionActionResponse(status="started")


@router.post("/stop", response_model=DetectionActionResponse)
async def stop_detection():
    await asyncio.to_thread(detection_service.stop)
    return DetectionActionResponse(status="stopped")


@router.get("/status", response_model=DetectionStatusResponse)
async def get_detection_status():
    # Plain REST snapshot — handy for a quick manual check via /docs without
    # needing a WebSocket client.
    return DetectionStatusResponse(**detection_service.get_status())


@router.websocket("/ws")
async def detection_status_stream(websocket: WebSocket):
    """Pushes detection status to the frontend at a fixed interval.

    Why polling the shared state on a timer instead of having the
    detection thread push directly: the detection loop runs in a plain
    threading.Thread, not asyncio — bridging that to a WebSocket cleanly
    means reading the thread-safe state from this async loop instead of
    trying to call async code from inside the worker thread.
    """
    await websocket.accept()
    try:
        while True:
            status = DetectionStatusResponse(**detection_service.get_status())
            await websocket.send_json(status.model_dump())
            await asyncio.sleep(settings.DETECTION_STATUS_PUSH_INTERVAL_SEC)
    except WebSocketDisconnect:
        logger.info("Detection status WebSocket client disconnected")

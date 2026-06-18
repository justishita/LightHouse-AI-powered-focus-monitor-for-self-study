"""
models/schemas.py — Pydantic models for request/response validation.

Why centralized: routers import response/request shapes from here rather
than defining inline dicts, so the API contract is explicit and
type-checked instead of implicit in whatever a service function returns.
"""

from typing import Optional

from pydantic import BaseModel


class DetectionStatusResponse(BaseModel):
    face_visible: bool
    looking_away: bool
    yaw_deg: float
    pitch_deg: float
    zoned_out_duration_sec: float
    gaze_alert: bool
    phone_detected: bool
    last_updated: float


class DetectionActionResponse(BaseModel):
    status: str  # "started" | "stopped" | "already_running" | "error"
    detail: Optional[str] = None

"""
config.py — Centralized application configuration.

Why a single config module: every other file (routers, services, main)
imports from here instead of calling os.getenv() directly. That means
if we ever need to change a default value, add a new setting, or swap
where settings come from, there's exactly one place to do it.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # --- App metadata ---
    APP_NAME: str = "SelfStudy API"
    APP_ENV: str = "development"  # "development" | "production"

    # --- CORS ---
    # Comma-separated list parsed into a list below. Kept as plain strings
    # in .env because env vars can't natively hold Python lists.
    CORS_ORIGINS: str = "http://localhost:5173"

    # --- Camera / detection ---
    CAMERA_INDEX: int = 0  # which webcam OpenCV should open (0 = default)
    DETECTION_FRAME_INTERVAL_SEC: float = 0.2  # gaze check frequency
    PHONE_CHECK_INTERVAL_SEC: float = 1.5      # phone detection runs less often — it's the heavier model
    DETECTION_STATUS_PUSH_INTERVAL_SEC: float = 0.5  # how often the WS pushes status to the frontend

    # --- Gaze / head pose ---
    # Starting points, not guaranteed-exact for every face/webcam — watch the
    # logged yaw/pitch while testing and tune these in .env if needed.
    GAZE_YAW_THRESHOLD_DEG: float = 30.0   # left/right turn beyond this = "looking away"
    GAZE_PITCH_THRESHOLD_DEG: float = 20.0  # up/down tilt beyond this = "looking away" (catches looking down at a phone in your lap too)
    GAZE_ALERT_THRESHOLD_SEC: float = 15.0  # how long "looking away" persists before triggering the alert

    # --- Phone detection ---
    PHONE_CONFIDENCE_THRESHOLD: float = 0.5  # minimum YOLO confidence to count as a phone

    # --- Gaze / head-pose thresholds ---
    # Degrees of yaw (turned left/right) or pitch (looking up/down) before
    # we consider the user "not looking at the screen". 25/20 are reasonable
    # starting points — turning to glance at a notebook briefly shouldn't
    # trip this, but turning away from the screen for a while should.
    HEAD_POSE_YAW_THRESHOLD_DEG: float = 25.0
    HEAD_POSE_PITCH_THRESHOLD_DEG: float = 20.0

    # How long gaze must be continuously "away" (or face not visible at all)
    # before it counts as a distraction worth alerting on.
    DISTRACTION_THRESHOLD_SEC: float = 15.0

    # --- Phone detection ---
    PHONE_CONFIDENCE_THRESHOLD: float = 0.5  # YOLO confidence floor for a "cell phone" box to count

    # --- Logging ---
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "selfstudy.log"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # ignore unexpected env vars instead of crashing
    )

    @property
    def cors_origins_list(self) -> list[str]:
        # Split + strip so "http://a, http://b" and "http://a,http://b" both work
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]


# Single shared instance — import this everywhere, don't instantiate Settings() elsewhere
settings = Settings()

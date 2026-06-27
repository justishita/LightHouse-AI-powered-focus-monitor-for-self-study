"""
config.py — Centralized application configuration.

Why a single config module: every other file (routers, services, main)
imports from here instead of calling os.getenv() directly. That means
if we ever need to change a default value, add a new setting, or swap
where settings come from, there's exactly one place to do it.
"""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Resolve paths relative to this file, not the cwd — so uvicorn can be
# launched from any directory without breaking relative file references.
_BACKEND_DIR = Path(__file__).resolve().parent


class Settings(BaseSettings):
    # --- App metadata ---
    APP_NAME: str = "SelfStudy API"
    APP_ENV: str = "development"  # "development" | "production"

    # --- CORS ---
    # Comma-separated so .env stays plain text. Parsed into a list via
    # the cors_origins_list property below.
    CORS_ORIGINS: str = "http://localhost:5173"

    # --- Database ---
    # Path is relative to the backend/ directory so the DB file always
    # lands next to main.py regardless of where uvicorn is invoked from.
    DB_PATH: str = str(_BACKEND_DIR / "selfstudy.db")

    # --- Camera / detection ---
    CAMERA_INDEX: int = 0
    DETECTION_FRAME_INTERVAL_SEC: float = 0.2   # gaze check frequency (seconds)
    PHONE_CHECK_INTERVAL_SEC: float = 1.5        # phone check less often — heavier model
    DETECTION_STATUS_PUSH_INTERVAL_SEC: float = 0.5  # WebSocket push cadence

    # --- Gaze / head-pose thresholds ---
    # Degrees of yaw (left/right turn) or pitch (up/down tilt) beyond which
    # the user is considered "not looking at the screen". Starting points —
    # watch logged yaw/pitch values during manual testing and tune in .env.
    GAZE_YAW_THRESHOLD_DEG: float = 30.0
    GAZE_PITCH_THRESHOLD_DEG: float = 20.0
    # How long gaze must be continuously away (or face absent) before
    # gaze_alert flips to True and the alert popup can fire.
    GAZE_ALERT_THRESHOLD_SEC: float = 15.0

    # --- Phone detection ---
    PHONE_CONFIDENCE_THRESHOLD: float = 0.5  # minimum YOLO confidence to count

    # --- Alerts ---
    # How long after a dismissal before another popup is allowed to fire,
    # even if the distraction condition is still active.
    ALERT_COOLDOWN_SEC: float = 120.0  # 2 minutes

    # --- Session tracking ---
    # How often session_service samples the detection state to bucket time
    # into focused vs. distracted. 1 s is fine — focus score doesn't need
    # sub-second precision, and a tighter loop would just burn CPU for no gain.
    SESSION_TICK_INTERVAL_SEC: float = 1.0

    # --- Logging ---
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "selfstudy.log"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


# Single shared instance imported everywhere — never instantiate Settings() directly
settings = Settings()

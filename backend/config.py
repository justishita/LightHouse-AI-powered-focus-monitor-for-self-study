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

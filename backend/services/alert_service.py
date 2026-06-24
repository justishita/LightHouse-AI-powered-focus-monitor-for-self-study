"""
services/alert_service.py — Trigger alerts, cooldown logic.

Why this is separate from detection_service: detection_service's only job
is producing a clean read of "what's happening right now" (gaze away?
phone visible?). Deciding WHEN that should actually interrupt the user
with a popup — and not re-firing every single tick the condition stays
true — is a distinct concern with its own state machine, so it gets its
own file rather than bloating detection_service with UX policy.

State machine (per your choices: one shared alert type/popup for both
triggers, manual dismiss only, 2-minute cooldown that starts on dismiss):

  idle     -> no popup showing, free to fire if a trigger condition is true
  active   -> popup showing, stays showing until dismiss() is called
              (no auto-dismiss, no re-firing while already active)
  cooldown -> just dismissed, won't fire again until ALERT_COOLDOWN_SEC has
              passed, even if the underlying distraction is still happening
              (otherwise dismissing mid-distraction would instantly refire
              on the very next detection tick)
"""

import threading
import time
from typing import Optional

from config import settings
from utils.logger import get_logger

logger = get_logger(__name__)


class AlertService:
    def __init__(self):
        self._lock = threading.Lock()
        self._state = "idle"  # "idle" | "active" | "cooldown"
        self._message: Optional[str] = None
        self._reason: Optional[str] = None  # "phone" | "gaze" | "both"
        self._cooldown_started_at: Optional[float] = None

    def evaluate(self, gaze_alert: bool, phone_detected: bool) -> dict:
        """Call on every detection tick. Advances the state machine based
        on current distraction signals and returns the current alert
        status for merging into the detection status payload."""
        with self._lock:
            now = time.time()

            if self._state == "cooldown":
                elapsed = now - self._cooldown_started_at
                if elapsed >= settings.ALERT_COOLDOWN_SEC:
                    self._state = "idle"

            if self._state == "idle" and (gaze_alert or phone_detected):
                self._fire(gaze_alert, phone_detected)

            return self._snapshot(now)

    def dismiss(self) -> dict:
        """User clicked the popup's dismiss button — close it and start
        the cooldown clock so it can't immediately refire."""
        with self._lock:
            now = time.time()
            if self._state != "active":
                # Harmless no-op — e.g. a stale frontend click arriving
                # after the alert already cleared some other way.
                logger.info(f"Dismiss called while state was '{self._state}' — no-op")
                return self._snapshot(now)

            self._state = "cooldown"
            self._cooldown_started_at = now
            self._message = None
            self._reason = None
            logger.info(f"Alert dismissed — cooldown for {settings.ALERT_COOLDOWN_SEC}s")
            return self._snapshot(now)

    def reset(self) -> None:
        """Called when a session starts/stops so leftover alert/cooldown
        state from a previous session never leaks into a new one."""
        with self._lock:
            self._state = "idle"
            self._message = None
            self._reason = None
            self._cooldown_started_at = None

    # ---------- internal ----------

    def _fire(self, gaze_alert: bool, phone_detected: bool) -> None:
        # Same popup/cooldown for both triggers — only the message text
        # differs, so the user knows *why* without it being a separate
        # alert type or having its own cooldown.
        if gaze_alert and phone_detected:
            self._reason = "both"
            self._message = "Phone detected and you've been looking away — refocus on your study session."
        elif phone_detected:
            self._reason = "phone"
            self._message = "Phone detected — refocus on your study session."
        else:
            self._reason = "gaze"
            self._message = "You've been looking away for a while — refocus on your study session."
        self._state = "active"
        logger.info(f"Alert triggered: reason={self._reason}")

    def _snapshot(self, now: float) -> dict:
        cooldown_remaining = 0.0
        if self._state == "cooldown" and self._cooldown_started_at:
            cooldown_remaining = max(
                0.0, settings.ALERT_COOLDOWN_SEC - (now - self._cooldown_started_at)
            )
        return {
            "alert_active": self._state == "active",
            "alert_message": self._message,
            "alert_reason": self._reason,
            "alert_cooldown_remaining_sec": round(cooldown_remaining, 1),
        }


# Single shared instance — same pattern as camera_service/detection_service
alert_service = AlertService()

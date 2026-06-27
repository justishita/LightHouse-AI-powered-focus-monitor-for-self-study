"""
services/session_service.py — Session lifecycle, time accounting, DB persistence.

Responsibilities:
  1. Start / stop a study session (which also controls detection + alert)
  2. Run a background tick loop that samples detection state every
     SESSION_TICK_INTERVAL_SEC and buckets time into focused vs. distracted
  3. Record distraction_events when alert_active flips True, close them when
     the alert is dismissed (alert_active flips False)
  4. Track the current unbroken focus streak and the session's max streak
  5. Save final aggregated stats to the sessions table on stop

Why session_service drives detection_service (rather than the router):
once we have sessions, "start detection" always means "start a session" —
keeping that coupling explicit here (not split across router and service)
makes the flow easy to trace and avoids double-start bugs.

Time accounting model:
  Each tick we read the combined distraction flag:
    distracted = gaze_alert OR phone_detected
  If distracted: add tick duration to distracted_sec, reset current streak
  If focused:    add tick duration to focused_sec, accumulate current streak
  Distraction_events in the DB mirror alert_service state (alert_active),
  not raw detection — one DB row per popup shown, with its reason + duration.
"""

import threading
import time
from typing import Optional

from config import settings
from services.alert_service import alert_service
from services.detection_service import detection_service
from utils.database import get_connection, init_db
from utils.logger import get_logger

logger = get_logger(__name__)


class _LiveStats:
    """Thread-safe in-memory accumulator for the current session."""

    def __init__(self, session_id: int, started_at: float):
        self._lock = threading.Lock()
        self.session_id = session_id
        self.started_at = started_at
        self.focused_sec: float = 0.0
        self.distracted_sec: float = 0.0
        # Streak tracking
        self._current_streak_start: float = started_at  # resets on each distraction
        self.max_streak_sec: float = 0.0
        self.distraction_count: int = 0
        # Used to detect alert_active transitions (False->True = new event)
        self._last_alert_active: bool = False
        self._open_event_id: Optional[int] = None  # DB id of an unclosed event

    def tick(self, focused: bool, alert_active: bool, alert_reason: Optional[str]) -> None:
        with self._lock:
            dt = settings.SESSION_TICK_INTERVAL_SEC
            now = time.time()

            if focused:
                self.focused_sec += dt
                streak = now - self._current_streak_start
                if streak > self.max_streak_sec:
                    self.max_streak_sec = streak
            else:
                self.distracted_sec += dt
                self._current_streak_start = now  # streak broken; restart clock

            # Detect alert rising edge (False -> True): open a DB event row
            if alert_active and not self._last_alert_active:
                self.distraction_count += 1
                self._open_event_id = _insert_event(
                    session_id=self.session_id,
                    started_at=now,
                    reason=alert_reason or "gaze",
                )
            # Detect alert falling edge (True -> False): close the open event row
            elif not alert_active and self._last_alert_active and self._open_event_id:
                _close_event(self._open_event_id, ended_at=now)
                self._open_event_id = None

            self._last_alert_active = alert_active

    def snapshot(self) -> dict:
        with self._lock:
            elapsed = self.focused_sec + self.distracted_sec
            focus_score = (self.focused_sec / elapsed * 100) if elapsed > 0 else 100.0
            current_streak_sec = time.time() - self._current_streak_start
            return {
                "session_id": self.session_id,
                "elapsed_sec": round(elapsed),
                "focused_sec": round(self.focused_sec),
                "distracted_sec": round(self.distracted_sec),
                "focus_score": round(focus_score, 1),
                "current_streak_min": round(current_streak_sec / 60, 1),
                "max_streak_min": round(self.max_streak_sec / 60, 1),
                "distraction_count": self.distraction_count,
            }


# --- DB helpers (module-level so they are testable in isolation) ---

def _insert_session(started_at: float) -> int:
    conn = get_connection()
    try:
        cur = conn.execute(
            "INSERT INTO sessions (started_at, distraction_count) VALUES (?, 0)",
            (started_at,),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def _close_session(session_id: int, stats: dict) -> None:
    conn = get_connection()
    try:
        conn.execute(
            """UPDATE sessions SET
               ended_at=?, duration_sec=?, focused_sec=?, distracted_sec=?,
               focus_score=?, max_streak_sec=?, distraction_count=?
               WHERE id=?""",
            (
                time.time(),
                stats["elapsed_sec"],
                stats["focused_sec"],
                stats["distracted_sec"],
                stats["focus_score"],
                # snapshot returns minutes; store raw seconds for precision
                stats["max_streak_min"] * 60,
                stats["distraction_count"],
                session_id,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def _insert_event(session_id: int, started_at: float, reason: str) -> int:
    conn = get_connection()
    try:
        cur = conn.execute(
            "INSERT INTO distraction_events (session_id, started_at, reason) VALUES (?,?,?)",
            (session_id, started_at, reason),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def _close_event(event_id: int, ended_at: float) -> None:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT started_at FROM distraction_events WHERE id=?", (event_id,)
        ).fetchone()
        started = row["started_at"] if row else ended_at
        conn.execute(
            "UPDATE distraction_events SET ended_at=?, duration_sec=? WHERE id=?",
            (ended_at, ended_at - started, event_id),
        )
        conn.commit()
    finally:
        conn.close()


# --- SessionService ---

class SessionService:
    def __init__(self):
        self._live: Optional[_LiveStats] = None
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    def start(self) -> dict:
        """Start a new session. Returns an error dict if one is already active."""
        if self._live is not None:
            return {"ok": False, "error": "A session is already in progress."}

        if not detection_service.start():
            return {"ok": False, "error": "Could not open webcam — is it in use?"}

        alert_service.reset()
        now = time.time()
        session_id = _insert_session(started_at=now)
        self._live = _LiveStats(session_id=session_id, started_at=now)

        self._stop_event.clear()
        self._thread = threading.Thread(target=self._tick_loop, daemon=True)
        self._thread.start()

        logger.info(f"Session {session_id} started")
        return {"ok": True, "session_id": session_id}

    def stop(self) -> dict:
        """Stop the current session, persist final stats, return a summary."""
        if self._live is None:
            return {"ok": False, "error": "No active session to stop."}

        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=3.0)

        stats = self._live.snapshot()
        _close_session(self._live.session_id, stats)
        detection_service.stop()
        alert_service.reset()

        logger.info(
            f"Session {self._live.session_id} stopped — "
            f"focus score: {stats['focus_score']}%"
        )
        self._live = None
        return {"ok": True, **stats}

    @property
    def is_active(self) -> bool:
        return self._live is not None

    def get_live_stats(self) -> Optional[dict]:
        """Returns current in-memory stats, or None if no session is running."""
        return self._live.snapshot() if self._live else None

    def _tick_loop(self) -> None:
        while not self._stop_event.is_set():
            status = detection_service.get_status()
            alert_status = alert_service.evaluate(
                gaze_alert=status["gaze_alert"],
                phone_detected=status["phone_detected"],
            )
            # focused = neither raw distraction signal is active. Using raw
            # signals (not alert_active) so brief away-looks under the 15s
            # threshold still accumulate distracted_sec even without a popup.
            focused = not (status["gaze_alert"] or status["phone_detected"])
            self._live.tick(
                focused=focused,
                alert_active=alert_status["alert_active"],
                alert_reason=alert_status["alert_reason"],
            )
            self._stop_event.wait(settings.SESSION_TICK_INTERVAL_SEC)


# Single shared instance
session_service = SessionService()


# --- Read-only DB helpers used by the session router ---

def get_session_history(limit: int = 50) -> list[dict]:
    """Return the most recent completed sessions, newest first."""
    conn = get_connection()
    try:
        rows = conn.execute(
            """SELECT id, started_at, ended_at, duration_sec, focus_score,
                      max_streak_sec, distraction_count
               FROM sessions
               WHERE ended_at IS NOT NULL
               ORDER BY started_at DESC
               LIMIT ?""",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_session_detail(session_id: int) -> Optional[dict]:
    """Return one session + its distraction events, or None if not found."""
    conn = get_connection()
    try:
        session = conn.execute(
            "SELECT * FROM sessions WHERE id=?", (session_id,)
        ).fetchone()
        if not session:
            return None
        events = conn.execute(
            """SELECT id, started_at, ended_at, duration_sec, reason
               FROM distraction_events WHERE session_id=? ORDER BY started_at""",
            (session_id,),
        ).fetchall()
        return {**dict(session), "events": [dict(e) for e in events]}
    finally:
        conn.close()

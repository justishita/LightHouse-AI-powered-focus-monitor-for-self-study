"""
utils/database.py — SQLite connection factory and schema initializer.

Why raw sqlite3 over SQLAlchemy: we have exactly two tables and no
complex joins — adding a full ORM would triple the dependency weight and
obscure what the schema actually looks like, which matters for a portfolio
project where a reviewer should be able to read the DB layer at a glance.

Why check_same_thread=False: SQLite connections are not thread-safe by
default, but we're using one connection per call (not one shared global
connection), so each thread always gets its own handle. check_same_thread
being False just stops SQLite from raising an error when a thread-local
connection is created outside the thread that opened it — we never share
a connection object across threads.

Why WAL mode: Write-Ahead Logging lets reads (history endpoint) and writes
(session stop) happen concurrently without blocking each other. With the
default journal mode, a write locks the whole file — fine for one user, but
WAL is a zero-cost habit worth keeping even in local dev.
"""

import sqlite3
from pathlib import Path

from config import settings
from utils.logger import get_logger

logger = get_logger(__name__)


def get_connection() -> sqlite3.Connection:
    """Open and return a new SQLite connection each time.

    Callers must close (or use `with` / try/finally) when done —
    no connection pooling, no long-lived shared connection.
    """
    conn = sqlite3.connect(settings.DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row  # rows behave like dicts: row["column"]
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")  # enforce ON DELETE CASCADE etc.
    return conn


def init_db() -> None:
    """Create tables if they don't already exist. Safe to call on every
    startup — IF NOT EXISTS makes it idempotent."""
    Path(settings.DB_PATH).parent.mkdir(parents=True, exist_ok=True)

    conn = get_connection()
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at      REAL    NOT NULL,   -- epoch seconds (time.time())
                ended_at        REAL,               -- NULL while session is in progress
                duration_sec    REAL,
                focused_sec     REAL,
                distracted_sec  REAL,
                -- focus_score = focused_sec / duration_sec * 100
                -- stored as a column so history queries can sort/filter cheaply
                -- without recomputing every time
                focus_score     REAL,
                -- longest unbroken focus run (seconds) within the session,
                -- converted to minutes in the API response layer
                max_streak_sec  REAL,
                distraction_count INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS distraction_events (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id  INTEGER NOT NULL REFERENCES sessions(id),
                started_at  REAL    NOT NULL,
                ended_at    REAL,               -- NULL if still ongoing
                duration_sec REAL,              -- filled on close
                -- "gaze" | "phone" | "both" — from alert_service's reason field
                reason      TEXT    NOT NULL
            );

            -- Index used by the history endpoint (ORDER BY started_at DESC)
            -- and by the live stats queries that filter WHERE id = ?
            CREATE INDEX IF NOT EXISTS idx_distraction_session
                ON distraction_events(session_id);
        """)
        conn.commit()
        logger.info(f"Database initialized at {settings.DB_PATH}")
    finally:
        conn.close()

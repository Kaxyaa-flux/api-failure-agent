"""
db.py — SQLite database initialisation and CRUD helpers.
"""

import sqlite3
import os
from datetime import datetime
from typing import Optional

DB_PATH = os.path.join(os.path.dirname(__file__), "logs.db")


def get_connection() -> sqlite3.Connection:
    """Return a connection with row_factory set to dict-like rows."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create tables if they don't exist."""
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS api_logs (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                endpoint    TEXT    NOT NULL,
                method      TEXT    NOT NULL,
                status_code INTEGER NOT NULL,
                latency     REAL    NOT NULL,
                timestamp   TEXT    NOT NULL,
                created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
            )
            """
        )
        conn.commit()


def insert_log(
    endpoint: str,
    method: str,
    status_code: int,
    latency: float,
    timestamp: str,
) -> int:
    """Insert a single log entry and return its new id."""
    now = datetime.utcnow().isoformat()
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO api_logs (endpoint, method, status_code, latency, timestamp, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (endpoint, method, status_code, latency, timestamp, now),
        )
        conn.commit()
        return cursor.lastrowid


def fetch_recent_logs(limit: int = 100) -> list[dict]:
    """Return the most recent `limit` logs, newest first."""
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, endpoint, method, status_code, latency, timestamp, created_at
            FROM api_logs
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


def fetch_logs_for_endpoint(endpoint: str, limit: int = 50) -> list[dict]:
    """Return up to `limit` most-recent logs for one endpoint."""
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, endpoint, method, status_code, latency, timestamp
            FROM api_logs
            WHERE endpoint = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (endpoint, limit),
        ).fetchall()
    return [dict(row) for row in rows]


def fetch_all_endpoints() -> list[str]:
    """Return distinct endpoints that have logs."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT DISTINCT endpoint FROM api_logs"
        ).fetchall()
    return [row["endpoint"] for row in rows]


def fetch_all_logs() -> list[dict]:
    """Return every log row (used for clustering)."""
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, endpoint, method, status_code, latency, timestamp
            FROM api_logs
            ORDER BY id DESC
            """
        ).fetchall()
    return [dict(row) for row in rows]

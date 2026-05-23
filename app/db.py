import sqlite3
from contextlib import contextmanager
import os

DB_PATH = "api_logs.db"

@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

def init_db():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                endpoint TEXT,
                method TEXT,
                status_code INTEGER,
                latency REAL,
                timestamp TEXT
            )
        """)
        conn.commit()

def insert_log(endpoint: str, method: str, status_code: int, latency: float, timestamp: str):
    with get_db() as conn:
        conn.execute(
            "INSERT INTO logs (endpoint, method, status_code, latency, timestamp) VALUES (?, ?, ?, ?, ?)",
            (endpoint, method, status_code, latency, timestamp)
        )
        conn.commit()

def get_recent_logs(limit: int = 100):
    with get_db() as conn:
        cursor = conn.execute("SELECT * FROM logs ORDER BY id DESC LIMIT ?", (limit,))
        return [dict(row) for row in cursor.fetchall()]

def get_logs_by_endpoint(endpoint: str, limit: int = 50):
    with get_db() as conn:
        cursor = conn.execute("SELECT * FROM logs WHERE endpoint = ? ORDER BY id DESC LIMIT ?", (endpoint, limit))
        return [dict(row) for row in cursor.fetchall()]

def get_all_endpoints():
    with get_db() as conn:
        cursor = conn.execute("SELECT DISTINCT endpoint FROM logs")
        return [row["endpoint"] for row in cursor.fetchall()]

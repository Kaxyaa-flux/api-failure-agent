import sqlite3
import json
from contextlib import contextmanager
from pathlib import Path
from datetime import datetime, timedelta, timezone

DB_PATH = Path(__file__).parent / "logs.db"

# Track whether WAL mode has been set for this process (set only once)
_wal_initialized = False


@contextmanager
def get_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    global _wal_initialized
    with get_db() as conn:
        # Set WAL mode once per process startup
        if not _wal_initialized:
            conn.execute("PRAGMA journal_mode=WAL")
            _wal_initialized = True
        conn.execute("""
            CREATE TABLE IF NOT EXISTS api_logs (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                endpoint   TEXT    NOT NULL,
                method     TEXT    NOT NULL,
                status_code INTEGER NOT NULL,
                latency    REAL    NOT NULL,
                timestamp  TEXT    NOT NULL,
                created_at TEXT    NOT NULL DEFAULT (datetime('now'))
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS alerts (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                endpoint   TEXT,
                anomaly_type TEXT,
                anomaly    TEXT,
                explanation TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_logs_endpoint ON api_logs(endpoint);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_alerts_endpoint_type ON alerts(endpoint, anomaly_type);")
        conn.commit()


def reset_db():
    with get_db() as conn:
        conn.execute("DELETE FROM api_logs")
        conn.execute("DELETE FROM alerts")
        conn.commit()


# ── Log helpers ────────────────────────────────────────────────────────────────

def insert_log(endpoint: str, method: str, status_code: int, latency: float, timestamp: str):
    with get_db() as conn:
        conn.execute(
            "INSERT INTO api_logs (endpoint, method, status_code, latency, timestamp) VALUES (?, ?, ?, ?, ?)",
            (endpoint, method, status_code, latency, timestamp)
        )
        conn.commit()


def fetch_recent_logs(limit: int = 100):
    with get_db() as conn:
        cur = conn.execute(
            "SELECT * FROM api_logs ORDER BY id DESC LIMIT ?", (limit,)
        )
        return [dict(row) for row in cur.fetchall()]


def fetch_logs_for_endpoint(endpoint: str, limit: int = 50):
    with get_db() as conn:
        cur = conn.execute(
            "SELECT * FROM api_logs WHERE endpoint = ? ORDER BY id DESC LIMIT ?",
            (endpoint, limit)
        )
        return [dict(row) for row in cur.fetchall()]


def fetch_all_endpoints():
    with get_db() as conn:
        cur = conn.execute("SELECT DISTINCT endpoint FROM api_logs")
        return [row["endpoint"] for row in cur.fetchall()]


def fetch_all_logs():
    with get_db() as conn:
        cur = conn.execute("SELECT * FROM api_logs ORDER BY id DESC")
        return [dict(row) for row in cur.fetchall()]


# ── Alert helpers ──────────────────────────────────────────────────────────────

def insert_alert(endpoint: str, anomaly: dict, explanation: dict):
    anomaly_type = anomaly.get("anomaly_type", "")
    with get_db() as conn:
        conn.execute(
            "INSERT INTO alerts (endpoint, anomaly_type, anomaly, explanation) VALUES (?, ?, ?, ?)",
            (endpoint, anomaly_type, json.dumps(anomaly), json.dumps(explanation))
        )
        conn.commit()


def fetch_recent_alerts(limit: int = 100):
    with get_db() as conn:
        cur = conn.execute(
            "SELECT * FROM alerts ORDER BY id DESC LIMIT ?", (limit,)
        )
        alerts = []
        for row in cur.fetchall():
            d = dict(row)
            d["anomaly"] = json.loads(d["anomaly"])
            d["explanation"] = json.loads(d["explanation"])
            alerts.append(d)
        return alerts


def has_recent_alert(endpoint: str, anomaly_type: str = "", within_minutes: int = 5) -> bool:
    """
    Returns True if an alert for the same (endpoint, anomaly_type) pair was
    already inserted within the last `within_minutes` minutes.
    Different anomaly types on the same endpoint are NOT suppressed together.
    """
    with get_db() as conn:
        if anomaly_type:
            cur = conn.execute(
                "SELECT created_at FROM alerts WHERE endpoint = ? AND anomaly_type = ? ORDER BY id DESC LIMIT 1",
                (endpoint, anomaly_type)
            )
        else:
            cur = conn.execute(
                "SELECT created_at FROM alerts WHERE endpoint = ? ORDER BY id DESC LIMIT 1",
                (endpoint,)
            )
        row = cur.fetchone()
        if not row:
            return False
        try:
            last_dt = datetime.fromisoformat(row["created_at"])
            # Normalise to UTC-aware before comparison
            if last_dt.tzinfo is None:
                last_dt = last_dt.replace(tzinfo=timezone.utc)
            now_utc = datetime.now(timezone.utc)
            return (now_utc - last_dt) <= timedelta(minutes=within_minutes)
        except ValueError:
            return False

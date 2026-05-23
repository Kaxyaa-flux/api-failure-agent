import sqlite3
import json
from contextlib import contextmanager
from pathlib import Path
from datetime import datetime, timedelta

DB_PATH = Path(__file__).parent / "api_logs.db"

@contextmanager
def get_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
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
        conn.execute("""
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                endpoint TEXT,
                anomaly TEXT,
                explanation TEXT,
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

def insert_alert(endpoint: str, anomaly: dict, explanation: dict, timestamp: str):
    with get_db() as conn:
        conn.execute(
            "INSERT INTO alerts (endpoint, anomaly, explanation, timestamp) VALUES (?, ?, ?, ?)",
            (endpoint, json.dumps(anomaly), json.dumps(explanation), timestamp)
        )
        conn.commit()

def get_recent_alerts(limit: int = 100):
    with get_db() as conn:
        cursor = conn.execute("SELECT * FROM alerts ORDER BY id DESC LIMIT ?", (limit,))
        alerts = []
        for row in cursor.fetchall():
            alert_dict = dict(row)
            alert_dict["anomaly"] = json.loads(alert_dict["anomaly"])
            alert_dict["explanation"] = json.loads(alert_dict["explanation"])
            alerts.append(alert_dict)
        return alerts

def has_recent_alert(endpoint: str, current_timestamp: str, within_minutes: int = 5) -> bool:
    with get_db() as conn:
        cursor = conn.execute("SELECT timestamp FROM alerts WHERE endpoint = ? ORDER BY id DESC LIMIT 1", (endpoint,))
        row = cursor.fetchone()
        if not row:
            return False
            
        last_timestamp_str = row["timestamp"]
        try:
            last_dt = datetime.fromisoformat(last_timestamp_str.replace("Z", "+00:00"))
            curr_dt = datetime.fromisoformat(current_timestamp.replace("Z", "+00:00"))
            return (curr_dt - last_dt) <= timedelta(minutes=within_minutes)
        except ValueError:
            return last_timestamp_str == current_timestamp

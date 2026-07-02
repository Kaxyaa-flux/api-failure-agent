import json
import os
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

import psycopg2
import psycopg2.extras

DATABASE_URL = os.environ.get("DATABASE_URL", "")


@contextmanager
def get_db():
    url = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    conn = psycopg2.connect(url, cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        yield conn
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS api_logs (
                    id          SERIAL PRIMARY KEY,
                    endpoint    TEXT    NOT NULL,
                    method      TEXT    NOT NULL,
                    status_code INTEGER NOT NULL,
                    latency     REAL    NOT NULL,
                    timestamp   TEXT    NOT NULL,
                    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS alerts (
                    id           SERIAL PRIMARY KEY,
                    endpoint     TEXT,
                    anomaly_type TEXT,
                    anomaly      TEXT,
                    explanation  TEXT,
                    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)
            cur.execute("CREATE INDEX IF NOT EXISTS idx_logs_endpoint ON api_logs(endpoint)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_alerts_endpoint_type ON alerts(endpoint, anomaly_type)")
        conn.commit()


def reset_db():
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM api_logs")
            cur.execute("DELETE FROM alerts")
        conn.commit()


def insert_log(endpoint: str, method: str, status_code: int, latency: float, timestamp: str):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO api_logs (endpoint, method, status_code, latency, timestamp) VALUES (%s, %s, %s, %s, %s)",
                (endpoint, method, status_code, latency, timestamp),
            )
        conn.commit()


def fetch_recent_logs(limit: int = 100):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM api_logs ORDER BY id DESC LIMIT %s", (limit,))
            return [dict(row) for row in cur.fetchall()]


def fetch_logs_for_endpoint(endpoint: str, limit: int = 50):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM api_logs WHERE endpoint = %s ORDER BY id DESC LIMIT %s",
                (endpoint, limit),
            )
            return [dict(row) for row in cur.fetchall()]


def fetch_all_endpoints():
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT DISTINCT endpoint FROM api_logs")
            return [row["endpoint"] for row in cur.fetchall()]


def insert_alert(endpoint: str, anomaly: dict, explanation: dict):
    anomaly_type = anomaly.get("anomaly_type", "")
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO alerts (endpoint, anomaly_type, anomaly, explanation) VALUES (%s, %s, %s, %s)",
                (endpoint, anomaly_type, json.dumps(anomaly), json.dumps(explanation)),
            )
        conn.commit()


def fetch_recent_alerts(limit: int = 100):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM alerts ORDER BY id DESC LIMIT %s", (limit,))
            alerts = []
            for row in cur.fetchall():
                d = dict(row)
                d["anomaly"] = json.loads(d["anomaly"])
                d["explanation"] = json.loads(d["explanation"])
                alerts.append(d)
            return alerts


def has_recent_alert(endpoint: str, anomaly_type: str = "", within_minutes: int = 5) -> bool:
    with get_db() as conn:
        with conn.cursor() as cur:
            if anomaly_type:
                cur.execute(
                    "SELECT created_at FROM alerts WHERE endpoint = %s AND anomaly_type = %s ORDER BY id DESC LIMIT 1",
                    (endpoint, anomaly_type),
                )
            else:
                cur.execute(
                    "SELECT created_at FROM alerts WHERE endpoint = %s ORDER BY id DESC LIMIT 1",
                    (endpoint,),
                )
            row = cur.fetchone()
            if not row:
                return False
            try:
                last_dt = row["created_at"]
                if isinstance(last_dt, str):
                    last_dt = datetime.fromisoformat(last_dt)
                if last_dt.tzinfo is None:
                    last_dt = last_dt.replace(tzinfo=timezone.utc)
                return (datetime.now(timezone.utc) - last_dt) <= timedelta(minutes=within_minutes)
            except (ValueError, TypeError):
                return False

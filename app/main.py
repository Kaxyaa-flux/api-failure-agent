from contextlib import asynccontextmanager
from datetime import datetime, timezone
import random

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import app.db as db
import app.anomaly as anomaly_mod
import app.cluster as cluster_mod
import app.llm as llm


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    yield


app = FastAPI(title="API Failure Detection Agent", lifespan=lifespan)

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Schema ────────────────────────────────────────────────────────────────────
class LogEntry(BaseModel):
    endpoint: str
    method: str
    status_code: int
    latency: float
    timestamp: datetime


# ── Routes ────────────────────────────────────────────────────────────────────

@app.post("/logs")
def ingest_log(log: LogEntry):
    ts = log.timestamp.isoformat()
    db.insert_log(
        endpoint=log.endpoint,
        method=log.method,
        status_code=log.status_code,
        latency=log.latency,
        timestamp=ts,
    )

    # Run anomaly detection for this endpoint
    ep_logs = db.fetch_logs_for_endpoint(log.endpoint, limit=50)
    detected = anomaly_mod.detect_anomalies(ep_logs)

    for anom in detected:
        if not db.has_recent_alert(anom["endpoint"], within_minutes=5):
            alert = llm.generate_alert(anom)
            db.insert_alert(anom["endpoint"], anom, alert)

    return {"status": "ok", "anomalies_detected": len(detected)}


@app.get("/logs")
def get_logs():
    return db.fetch_recent_logs(100)


@app.get("/anomalies")
def get_anomalies():
    all_logs = db.fetch_recent_logs(500)
    return anomaly_mod.detect_anomalies(all_logs)


@app.get("/clusters")
def get_clusters():
    logs = db.fetch_all_logs()
    return cluster_mod.cluster_failures(logs)


@app.get("/alerts")
def get_alerts():
    rows = db.fetch_recent_alerts(limit=100)
    # Flatten: return the explanation dict enriched with DB metadata
    alerts = []
    for row in rows:
        alert = row["explanation"]
        alert["db_id"] = row["id"]
        alert["created_at"] = row.get("created_at", "")
        alerts.append(alert)
    return alerts


@app.get("/health")
def health():
    return {"status": "ok", "service": "API Failure Detection Agent"}


@app.post("/seed")
def seed_data():
    """
    Inject anomalous synthetic traffic into /api/payment:
      - Every 5th request returns HTTP 500
      - Every 7th request gets a latency spike (1500–3000 ms)
    """
    endpoints = [
        "/api/payment",
        "/api/users",
        "/api/orders",
        "/api/inventory",
        "/api/auth",
    ]
    methods = ["GET", "POST", "PUT", "DELETE"]
    seeded = 0

    for i in range(60):
        ep = random.choice(endpoints)
        method = random.choice(methods)
        latency = round(random.uniform(80, 400), 2)
        status = 200

        # Force anomaly pattern on /api/payment
        if ep == "/api/payment":
            if (i + 1) % 5 == 0:
                status = 500
            if (i + 1) % 7 == 0:
                latency = round(random.uniform(1500, 3000), 2)

        ts = datetime.now(timezone.utc).isoformat()
        db.insert_log(
            endpoint=ep,
            method=method,
            status_code=status,
            latency=latency,
            timestamp=ts,
        )
        seeded += 1

    # Trigger anomaly detection after seeding
    ep_logs = db.fetch_logs_for_endpoint("/api/payment", limit=50)
    detected = anomaly_mod.detect_anomalies(ep_logs)
    for anom in detected:
        if not db.has_recent_alert(anom["endpoint"], within_minutes=1):
            alert = llm.generate_alert(anom)
            db.insert_alert(anom["endpoint"], anom, alert)

    return {"status": "ok", "logs_seeded": seeded, "anomalies_found": len(detected)}

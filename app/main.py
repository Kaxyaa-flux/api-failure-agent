from contextlib import asynccontextmanager
from datetime import datetime, timezone
import random

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, field_validator

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

_VALID_METHODS = {"GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"}


# ── Schema ────────────────────────────────────────────────────────────────────
class LogEntry(BaseModel):
    endpoint: str
    method: str
    status_code: int
    latency: float
    timestamp: datetime

    @field_validator("status_code")
    @classmethod
    def validate_status_code(cls, v: int) -> int:
        if not (100 <= v <= 599):
            raise ValueError(f"status_code must be between 100 and 599, got {v}")
        return v

    @field_validator("latency")
    @classmethod
    def validate_latency(cls, v: float) -> float:
        if v < 0:
            raise ValueError(f"latency must be >= 0, got {v}")
        return v

    @field_validator("method")
    @classmethod
    def validate_method(cls, v: str) -> str:
        upper = v.upper()
        if upper not in _VALID_METHODS:
            raise ValueError(f"method must be one of {_VALID_METHODS}, got {v!r}")
        return upper


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/", include_in_schema=False)
async def root():
    return RedirectResponse(url="/docs")


@app.post("/logs")
async def ingest_log(log: LogEntry):
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
        anom_type = anom.get("anomaly_type", "")
        if not db.has_recent_alert(anom["endpoint"], anomaly_type=anom_type, within_minutes=5):
            alert = llm.generate_alert(anom)
            db.insert_alert(anom["endpoint"], anom, alert)

    return {"status": "ok", "anomalies_detected": len(detected)}


@app.get("/logs")
async def get_logs():
    return db.fetch_recent_logs(1000)


@app.get("/anomalies")
async def get_anomalies():
    all_logs = db.fetch_recent_logs(500)
    return anomaly_mod.detect_anomalies(all_logs)


@app.get("/clusters")
async def get_clusters():
    # Cap at 2000 rows — avoids full-table scan on every 5-second poll
    logs = db.fetch_recent_logs(limit=2000)
    return cluster_mod.cluster_failures(logs)


@app.get("/alerts")
async def get_alerts():
    """
    1. Run live anomaly detection against recent logs.
    2. For any anomaly that has no alert within the cooldown window,
       generate one now and persist it.
    3. Return all persisted alerts (flat dicts), sorted newest-first.
    """
    # Live detection pass
    all_logs = db.fetch_recent_logs(500)
    detected = anomaly_mod.detect_anomalies(all_logs)
    for anom in detected:
        if not db.has_recent_alert(anom["endpoint"], anomaly_type=anom.get("anomaly_type", ""), within_minutes=5):
            alert = llm.generate_alert(anom)
            db.insert_alert(anom["endpoint"], anom, alert)

    # Fetch all persisted alerts and return as flat objects
    rows = db.fetch_recent_alerts(limit=1000)
    result = []
    for row in rows:
        flat = dict(row["explanation"])   # top-level: issue, severity, etc.
        flat["db_id"]     = row["id"]
        flat["created_at"] = row.get("created_at", "")
        flat["endpoint"]  = row.get("endpoint") or flat.get("endpoint", "")
        # Make sure anomaly_type is surfaced
        flat.setdefault("anomaly_type", row["anomaly"].get("anomaly_type", ""))
        result.append(flat)
    return result


@app.get("/health")
async def health():
    return {"status": "ok", "service": "API Failure Detection Agent"}


@app.post("/seed")
async def seed_data():
    """
    Inject anomalous synthetic traffic into multiple endpoints.
    Anomaly patterns are applied to every endpoint proportionally.
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
    all_detected = []

    for i in range(60):
        ep = random.choice(endpoints)
        method = random.choice(methods)
        latency = round(random.uniform(80, 400), 2)
        status = 200

        # Apply anomaly patterns uniformly across all endpoints
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

    # Trigger anomaly detection for ALL seeded endpoints
    for ep in endpoints:
        ep_logs = db.fetch_logs_for_endpoint(ep, limit=50)
        detected = anomaly_mod.detect_anomalies(ep_logs)
        for anom in detected:
            anom_type = anom.get("anomaly_type", "")
            if not db.has_recent_alert(anom["endpoint"], anomaly_type=anom_type, within_minutes=1):
                alert = llm.generate_alert(anom)
                db.insert_alert(anom["endpoint"], anom, alert)
        all_detected.extend(detected)

    return {
        "status": "ok",
        "logs_seeded": seeded,
        "anomalies_found": len(all_detected),
    }

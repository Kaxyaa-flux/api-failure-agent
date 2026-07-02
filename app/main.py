from contextlib import asynccontextmanager
from datetime import datetime, timezone
import random
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, field_validator
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

import app.db as db
import app.anomaly as anomaly_mod
import app.cluster as cluster_mod
import app.llm as llm

limiter = Limiter(key_func=get_remote_address)

@asynccontextmanager
async def lifespan(application: FastAPI):
    db.init_db()
    yield

app = FastAPI(title="API Failure Detection Agent", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

_raw_origins = os.environ.get("ALLOWED_ORIGINS", "*")
_origins = [o.strip() for o in _raw_origins.split(",")] if _raw_origins != "*" else ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

_VALID_METHODS = {"GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"}


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


@app.post("/logs")
@limiter.limit("120/minute")
async def ingest_log(request: Request, log: LogEntry):
    ts = log.timestamp.isoformat()
    db.insert_log(endpoint=log.endpoint, method=log.method, status_code=log.status_code, latency=log.latency, timestamp=ts)
    ep_logs = db.fetch_logs_for_endpoint(log.endpoint, limit=anomaly_mod.WINDOW_SIZE)
    detected = anomaly_mod.detect_anomalies(ep_logs)
    for anom in detected:
        anom_type = anom.get("anomaly_type", "")
        if not db.has_recent_alert(anom["endpoint"], anomaly_type=anom_type, within_minutes=5):
            alert = llm.generate_alert(anom)
            db.insert_alert(anom["endpoint"], anom, alert)
    return {"status": "ok", "anomalies_detected": len(detected)}


@app.get("/logs")
@limiter.limit("60/minute")
async def get_logs(request: Request):
    return db.fetch_recent_logs(1000)


@app.get("/anomalies")
@limiter.limit("60/minute")
async def get_anomalies(request: Request):
    return anomaly_mod.detect_anomalies(db.fetch_recent_logs(500))


@app.get("/clusters")
@limiter.limit("60/minute")
async def get_clusters(request: Request):
    return cluster_mod.cluster_failures(db.fetch_recent_logs(2000))


@app.get("/alerts")
@limiter.limit("60/minute")
async def get_alerts(request: Request):
    rows = db.fetch_recent_alerts(limit=1000)
    result = []
    for row in rows:
        flat = dict(row["explanation"])
        flat["db_id"] = row["id"]
        flat["created_at"] = str(row.get("created_at", ""))
        flat["endpoint"] = row.get("endpoint") or flat.get("endpoint", "")
        flat.setdefault("anomaly_type", row["anomaly"].get("anomaly_type", ""))
        result.append(flat)
    return result


@app.get("/status")
@limiter.limit("60/minute")
async def get_status(request: Request):
    logs = db.fetch_recent_logs(1000)
    alerts_raw = db.fetch_recent_alerts(limit=1000)
    alerts = []
    for row in alerts_raw:
        flat = dict(row["explanation"])
        flat["db_id"] = row["id"]
        flat["created_at"] = str(row.get("created_at", ""))
        flat["endpoint"] = row.get("endpoint") or flat.get("endpoint", "")
        flat.setdefault("anomaly_type", row["anomaly"].get("anomaly_type", ""))
        alerts.append(flat)
    return {"logs": logs, "alerts": alerts, "anomalies": anomaly_mod.detect_anomalies(logs), "clusters": cluster_mod.cluster_failures(logs)}


@app.get("/health")
async def health():
    return {"status": "ok", "service": "API Failure Detection Agent"}


@app.delete("/reset")
@limiter.limit("5/minute")
async def reset_data(request: Request, secret: str = ""):
    expected = os.environ.get("RESET_SECRET", "")
    if expected and secret != expected:
        raise HTTPException(status_code=403, detail="Invalid secret")
    db.reset_db()
    return {"status": "ok", "message": "Database reset"}


@app.post("/seed")
@limiter.limit("10/minute")
async def seed_data(request: Request):
    endpoints = ["/api/payment", "/api/users", "/api/orders", "/api/inventory", "/api/auth"]
    methods = ["GET", "POST", "PUT", "DELETE"]
    seeded = 0
    all_detected = []
    for i in range(60):
        ep = random.choice(endpoints)
        method = random.choice(methods)
        latency = round(random.uniform(80, 400), 2)
        status = 200
        if (i + 1) % 5 == 0:
            status = 500
        if (i + 1) % 7 == 0:
            latency = round(random.uniform(1500, 3000), 2)
        db.insert_log(endpoint=ep, method=method, status_code=status, latency=latency, timestamp=datetime.now(timezone.utc).isoformat())
        seeded += 1
    for ep in endpoints:
        ep_logs = db.fetch_logs_for_endpoint(ep, limit=anomaly_mod.WINDOW_SIZE)
        detected = anomaly_mod.detect_anomalies(ep_logs)
        for anom in detected:
            if not db.has_recent_alert(anom["endpoint"], anomaly_type=anom.get("anomaly_type", ""), within_minutes=1):
                db.insert_alert(anom["endpoint"], anom, llm.generate_alert(anom))
        all_detected.extend(detected)
    return {"status": "ok", "logs_seeded": seeded, "anomalies_found": len(all_detected)}


# Serve React frontend — must be LAST
_DIST = Path(__file__).parent.parent / "dashboard" / "dist"

if _DIST.exists():
    app.mount("/assets", StaticFiles(directory=str(_DIST / "assets")), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_frontend(full_path: str):
        return FileResponse(str(_DIST / "index.html"))
else:
    @app.get("/", include_in_schema=False)
    async def root():
        return RedirectResponse(url="/docs")

"""
main.py — FastAPI application entry point.

Endpoints
---------
POST /logs          Ingest a single API log entry
GET  /logs          Return the last 100 logs
GET  /anomalies     Detect and return anomalies across all endpoints
GET  /clusters      Return failure clusters grouped by endpoint + status_code
GET  /alerts        Generate AI-powered (or mock) alerts for current anomalies
GET  /health        Quick liveness check
POST /seed          (Dev helper) seed the DB with realistic demo data
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta
from typing import Any

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

from app.db import init_db, insert_log, fetch_recent_logs
from app.anomaly import detect_anomalies
from app.cluster import cluster_failures
from app.llm import generate_alerts

# ── app setup ──────────────────────────────────────────────────────────────

app = FastAPI(
    title="API Failure Detection Agent",
    description=(
        "Ingests API logs, detects anomalies, clusters failures, "
        "and generates AI-powered alerts."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",   # fallback for CRA / other ports
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    init_db()


# ── schemas ────────────────────────────────────────────────────────────────

class LogEntry(BaseModel):
    endpoint: str = Field(..., example="/api/payment")
    method: str = Field(..., example="GET")
    status_code: int = Field(..., example=200)
    latency: float = Field(..., example=120.0, description="Response time in milliseconds")
    timestamp: str = Field(..., example="2026-05-24T10:00:00")


class LogResponse(BaseModel):
    id: int
    endpoint: str
    method: str
    status_code: int
    latency: float
    timestamp: str
    created_at: str


# ── endpoints ──────────────────────────────────────────────────────────────

@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url="/docs")


@app.get("/health", tags=["Meta"])
def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "api-failure-agent"}


@app.post(
    "/logs",
    status_code=status.HTTP_201_CREATED,
    tags=["Logs"],
    summary="Ingest a single API log entry",
)
def ingest_log(entry: LogEntry) -> dict[str, Any]:
    # Basic timestamp validation
    try:
        datetime.fromisoformat(entry.timestamp)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="timestamp must be ISO-8601 format, e.g. 2026-05-24T10:00:00",
        )

    log_id = insert_log(
        endpoint=entry.endpoint,
        method=entry.method.upper(),
        status_code=entry.status_code,
        latency=entry.latency,
        timestamp=entry.timestamp,
    )
    return {"id": log_id, "message": "Log ingested successfully"}


@app.get(
    "/logs",
    tags=["Logs"],
    summary="Return the last 100 log entries (newest first)",
)
def get_logs() -> list[dict[str, Any]]:
    return fetch_recent_logs(limit=100)


@app.get(
    "/anomalies",
    tags=["Detection"],
    summary="Detect latency spikes and high error rates",
)
def get_anomalies() -> list[dict[str, Any]]:
    return detect_anomalies()


@app.get(
    "/clusters",
    tags=["Detection"],
    summary="Group failures by endpoint and status code",
)
def get_clusters() -> list[dict[str, Any]]:
    return cluster_failures()


@app.get(
    "/alerts",
    tags=["Alerts"],
    summary="Generate AI-powered alerts for current anomalies",
)
def get_alerts() -> list[dict[str, Any]]:
    anomalies = detect_anomalies()
    if not anomalies:
        return []
    return generate_alerts(anomalies)


# ── dev helper: seed realistic demo data ──────────────────────────────────

_ENDPOINTS = [
    "/api/payment",
    "/api/auth/login",
    "/api/users",
    "/api/orders",
    "/api/products",
]

_METHODS = ["GET", "POST", "PUT", "DELETE"]

_STATUS_WEIGHTS = [
    (200, 60),
    (201, 10),
    (400, 8),
    (401, 5),
    (403, 3),
    (404, 7),
    (500, 5),
    (503, 2),
]

_STATUS_POOL = [
    sc for sc, w in _STATUS_WEIGHTS for _ in range(w)
]


def _random_latency(status_code: int) -> float:
    """Return a plausible latency (ms) that correlates with status code."""
    base = random.gauss(mu=150, sigma=40)
    if status_code >= 500:
        base = random.gauss(mu=800, sigma=200)
    elif status_code >= 400:
        base = random.gauss(mu=250, sigma=60)
    return max(10.0, round(base, 2))


@app.post(
    "/seed",
    tags=["Dev"],
    summary="Seed the database with realistic demo logs (dev only)",
)
def seed_demo_data(count: int = 120) -> dict[str, Any]:
    """
    Insert `count` synthetic log entries spread over the past 2 hours.
    Intentionally injects anomalous patterns into /api/payment so the
    anomaly detector has something to find.
    """
    now = datetime.utcnow()
    inserted = 0

    for i in range(count):
        endpoint = random.choice(_ENDPOINTS)
        method = random.choice(_METHODS)
        status_code = random.choice(_STATUS_POOL)
        ts = now - timedelta(seconds=random.randint(0, 7200))

        # Force anomalies into /api/payment
        if endpoint == "/api/payment":
            if i % 5 == 0:
                # 500 error burst → high error rate
                status_code = random.choice([500, 503, 504])
            if i % 7 == 0:
                # extreme latency spike
                latency = random.uniform(1500, 4000)
            else:
                latency = _random_latency(status_code)
        else:
            latency = _random_latency(status_code)

        insert_log(
            endpoint=endpoint,
            method=method,
            status_code=status_code,
            latency=round(latency, 2),
            timestamp=ts.isoformat(),
        )
        inserted += 1

    return {"inserted": inserted, "message": "Demo data seeded successfully"}

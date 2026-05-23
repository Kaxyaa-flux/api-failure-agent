from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any
from datetime import datetime
from contextlib import asynccontextmanager
import time

import app.db as db
import app.anomaly as anomaly
import app.cluster as cluster
import app.llm as llm

@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    yield

app = FastAPI(title="API Failure Detection & Debugging Backend", lifespan=lifespan)

# Simple cache for clusters (TTL = 5 seconds) to avoid heavy DB queries on every poll
_CLUSTER_CACHE = {"timestamp": 0, "data": []}

# CORS setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class LogEntry(BaseModel):
    endpoint: str
    method: str
    status_code: int
    latency: float
    timestamp: datetime

@app.post("/logs")
def ingest_log(log: LogEntry):
    # Store log
    timestamp_str = log.timestamp.isoformat()
    db.insert_log(
        endpoint=log.endpoint,
        method=log.method,
        status_code=log.status_code,
        latency=log.latency,
        timestamp=timestamp_str
    )
    
    # Process for anomaly detection
    endpoint_logs = db.get_logs_by_endpoint(log.endpoint, limit=50)
    detected_anomaly = anomaly.detect_anomalies(endpoint_logs)
    
    if detected_anomaly:
        # Deduplication: Check if we alerted recently for this endpoint
        if not db.has_recent_alert(detected_anomaly["endpoint"], timestamp_str, within_minutes=5):
            explanation = llm.generate_explanation(detected_anomaly)
            db.insert_alert(detected_anomaly["endpoint"], detected_anomaly, explanation, timestamp_str)
                
    return {"status": "success", "message": "Log ingested successfully"}

@app.get("/logs")
def get_logs():
    return db.get_recent_logs(limit=100)

@app.get("/anomalies")
def get_anomalies():
    endpoints = db.get_all_endpoints()
    anomalies = []
    for ep in endpoints:
        logs = db.get_logs_by_endpoint(ep, limit=50)
        anom = anomaly.detect_anomalies(logs)
        if anom:
            anomalies.append(anom)
    return anomalies

@app.get("/cluster")
def get_clusters():
    current_time = time.time()
    if current_time - _CLUSTER_CACHE["timestamp"] < 5:
        return _CLUSTER_CACHE["data"]
        
    logs = db.get_recent_logs(limit=1000)
    result = cluster.cluster_failures(logs)
    
    _CLUSTER_CACHE["timestamp"] = current_time
    _CLUSTER_CACHE["data"] = result
    return result

@app.get("/alerts")
def get_alerts():
    return db.get_recent_alerts(limit=100)

@app.get("/")
def read_root():
    return {
        "status": "online",
        "message": "AI-Powered API Failure Detection Backend is running!",
        "endpoints": ["/docs", "/logs", "/anomalies", "/cluster", "/alerts"]
    }

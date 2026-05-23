from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any

import app.db as db
import app.anomaly as anomaly
import app.cluster as cluster
import app.llm as llm

app = FastAPI(title="API Failure Detection & Debugging Backend")

# In-memory alerts store
ALERTS = []

# CORS setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def startup_event():
    db.init_db()

class LogEntry(BaseModel):
    endpoint: str
    method: str
    status_code: int
    latency: float
    timestamp: str

@app.post("/logs")
def ingest_log(log: LogEntry):
    # Store log
    db.insert_log(
        endpoint=log.endpoint,
        method=log.method,
        status_code=log.status_code,
        latency=log.latency,
        timestamp=log.timestamp
    )
    
    # Process for anomaly detection
    endpoint_logs = db.get_logs_by_endpoint(log.endpoint, limit=50)
    detected_anomaly = anomaly.detect_anomalies(endpoint_logs)
    
    if detected_anomaly:
        # Check if we already alerted for this timestamp to prevent spam
        if not any(a["anomaly"]["timestamp"] == detected_anomaly["timestamp"] and a["anomaly"]["endpoint"] == detected_anomaly["endpoint"] for a in ALERTS):
            explanation = llm.generate_explanation(detected_anomaly)
            
            alert = {
                "anomaly": detected_anomaly,
                "explanation": explanation
            }
            ALERTS.append(alert)
            # keep only recent 100 alerts
            if len(ALERTS) > 100:
                ALERTS.pop(0)
                
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
    logs = db.get_recent_logs(limit=1000)
    return cluster.cluster_failures(logs)

@app.get("/alerts")
def get_alerts():
    # Return reversed to show newest first
    return list(reversed(ALERTS))

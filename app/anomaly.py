from typing import List, Dict, Optional

def detect_anomalies(logs: List[Dict]) -> Optional[Dict]:
    if not logs:
        return None
        
    # Calculate average latency from baseline (excluding the latest log if we have history)
    latencies = [log["latency"] for log in logs]
    baseline_latencies = latencies[1:] if len(latencies) > 1 else latencies
    avg_latency = sum(baseline_latencies) / len(baseline_latencies) if baseline_latencies else 0.0
    
    # Check latest log
    latest_log = logs[0]
    latest_latency = latest_log["latency"]
    
    # Calculate error rate (status >= 500)
    error_count = sum(1 for log in logs if log["status_code"] >= 500)
    error_rate = error_count / len(logs) if logs else 0.0
    
    # Anomaly conditions
    is_anomaly = False
    
    # Require at least 5 logs to establish a baseline
    if len(logs) >= 5:
        if avg_latency > 0 and latest_latency > (2 * avg_latency):
            is_anomaly = True
        if error_rate > 0.20:
            is_anomaly = True
            
    if is_anomaly:
        return {
            "endpoint": latest_log["endpoint"],
            "avg_latency": round(avg_latency, 2),
            "latest_latency": latest_latency,
            "error_rate": round(error_rate, 2),
            "timestamp": latest_log["timestamp"]
        }
    return None

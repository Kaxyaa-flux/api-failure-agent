def detect_anomalies(logs):
    if not logs:
        return None
        
    # Calculate average latency
    latencies = [log["latency"] for log in logs]
    avg_latency = sum(latencies) / len(latencies) if latencies else 0.0
    
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
            
        # Basic check for sudden drop in request volume
        # If the latest request was long after the others relative to the period, could be a drop
        # But for MVP, latency and error rate are primary indicators.
            
    if is_anomaly:
        return {
            "endpoint": latest_log["endpoint"],
            "avg_latency": round(avg_latency, 2),
            "latest_latency": latest_latency,
            "error_rate": round(error_rate, 2),
            "timestamp": latest_log["timestamp"]
        }
    return None

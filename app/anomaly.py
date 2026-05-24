from typing import List, Dict

WINDOW_SIZE = 50
LATENCY_MULTIPLIER = 2.0
ERROR_RATE_THRESHOLD = 0.20
# Number of recent points to average for spike detection (rolling window head)
SPIKE_HEAD = 3


def detect_anomalies(logs: List[Dict]) -> List[Dict]:
    """
    Analyse logs grouped by endpoint and return a list of anomaly dicts.
    Each dict has: endpoint, anomaly_type, description, severity,
                   value, threshold, sample_size, recent_status_codes.
    No `timestamp` field is emitted.
    """
    if not logs:
        return []

    # Group by endpoint
    by_endpoint: Dict[str, List[Dict]] = {}
    for log in logs:
        ep = log["endpoint"]
        by_endpoint.setdefault(ep, []).append(log)

    anomalies: List[Dict] = []

    for endpoint, ep_logs in by_endpoint.items():
        # Take at most WINDOW_SIZE newest records (already newest-first from DB)
        window = ep_logs[:WINDOW_SIZE]
        n = len(window)

        if n < 5:
            continue  # not enough data to establish a baseline

        latencies = [l["latency"] for l in window]
        status_codes = [l["status_code"] for l in window]

        # ── Latency spike: rolling window head vs baseline ─────────────────
        # Use the average of the SPIKE_HEAD most-recent samples as the "current"
        # reading, and the remaining samples as the baseline.  This avoids
        # false positives caused by a single noisy data point.
        head_count = min(SPIKE_HEAD, n - 2)  # must leave at least 2 for baseline
        head_latencies = latencies[:head_count]
        baseline_latencies = latencies[head_count:]

        recent_avg = sum(head_latencies) / len(head_latencies)
        avg_baseline = sum(baseline_latencies) / len(baseline_latencies)
        threshold_latency = avg_baseline * LATENCY_MULTIPLIER

        if avg_baseline > 0 and recent_avg > threshold_latency:
            severity = (
                "critical" if recent_avg > avg_baseline * 4
                else "high" if recent_avg > avg_baseline * 3
                else "medium"
            )
            anomalies.append({
                "endpoint": endpoint,
                "anomaly_type": "latency_spike",
                "description": (
                    f"Recent avg latency {recent_avg:.0f}ms (last {head_count} reqs) is "
                    f"{recent_avg / avg_baseline:.1f}x the baseline avg "
                    f"{avg_baseline:.0f}ms"
                ),
                "severity": severity,
                "value": round(recent_avg, 2),
                "threshold": round(threshold_latency, 2),
                "sample_size": n,
                "recent_status_codes": status_codes[:10],
            })

        # ── High error rate: 4xx/5xx share > 20 % ────────────────────────
        error_count = sum(1 for sc in status_codes if sc >= 400)
        error_rate = error_count / n
        threshold_rate = ERROR_RATE_THRESHOLD

        if error_rate > threshold_rate:
            severity = (
                "critical" if error_rate > 0.60
                else "high" if error_rate > 0.40
                else "medium"
            )
            anomalies.append({
                "endpoint": endpoint,
                "anomaly_type": "high_error_rate",
                "description": (
                    f"Error rate {error_rate * 100:.1f}% exceeds "
                    f"threshold {threshold_rate * 100:.0f}% "
                    f"({error_count}/{n} requests failed)"
                ),
                "severity": severity,
                "value": round(error_rate, 4),
                "threshold": threshold_rate,
                "sample_size": n,
                "recent_status_codes": status_codes[:10],
            })

    return anomalies

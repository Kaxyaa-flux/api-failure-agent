"""
anomaly.py — Anomaly detection logic.

Rules (per endpoint, last 50 requests):
  1. Latency spike  : latest latency > 2x the rolling average
  2. High error rate: 4xx/5xx share > 20 %
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from app.db import fetch_logs_for_endpoint, fetch_all_endpoints

# ── constants ──────────────────────────────────────────────────────────────
WINDOW = 50          # rolling window size
LATENCY_MULTIPLIER = 2.0   # spike threshold
ERROR_RATE_THRESHOLD = 0.20  # 20 %


@dataclass
class Anomaly:
    endpoint: str
    anomaly_type: str          # "latency_spike" | "high_error_rate"
    description: str
    severity: str              # "low" | "medium" | "high"
    value: float               # the observed metric value
    threshold: float           # the threshold that was exceeded
    sample_size: int           # number of requests analysed
    recent_status_codes: list[int] = field(default_factory=list)


def _severity_from_ratio(ratio: float) -> str:
    if ratio >= 4:
        return "high"
    if ratio >= 2.5:
        return "medium"
    return "low"


def _error_severity(rate: float) -> str:
    if rate >= 0.5:
        return "high"
    if rate >= 0.35:
        return "medium"
    return "low"


def detect_anomalies() -> list[dict]:
    """
    Run anomaly detection across all known endpoints and return
    a list of anomaly dicts ready for JSON serialisation.
    """
    endpoints = fetch_all_endpoints()
    anomalies: list[Anomaly] = []

    for endpoint in endpoints:
        logs = fetch_logs_for_endpoint(endpoint, limit=WINDOW)
        if len(logs) < 3:
            # Not enough data to make a meaningful decision
            continue

        latencies = [row["latency"] for row in logs]
        status_codes = [row["status_code"] for row in logs]

        # ── 1. Latency spike detection ────────────────────────────────────
        avg_latency = sum(latencies[1:]) / (len(latencies) - 1)  # exclude latest
        latest_latency = latencies[0]  # newest first

        if avg_latency > 0 and latest_latency > LATENCY_MULTIPLIER * avg_latency:
            ratio = latest_latency / avg_latency
            anomalies.append(
                Anomaly(
                    endpoint=endpoint,
                    anomaly_type="latency_spike",
                    description=(
                        f"Latest request to {endpoint} took {latest_latency:.1f} ms, "
                        f"which is {ratio:.1f}x the rolling average of {avg_latency:.1f} ms."
                    ),
                    severity=_severity_from_ratio(ratio),
                    value=latest_latency,
                    threshold=LATENCY_MULTIPLIER * avg_latency,
                    sample_size=len(logs),
                    recent_status_codes=status_codes[:10],
                )
            )

        # ── 2. High error rate detection ──────────────────────────────────
        error_count = sum(1 for sc in status_codes if sc >= 400)
        error_rate = error_count / len(status_codes)

        if error_rate > ERROR_RATE_THRESHOLD:
            anomalies.append(
                Anomaly(
                    endpoint=endpoint,
                    anomaly_type="high_error_rate",
                    description=(
                        f"{endpoint} has a {error_rate*100:.1f}% error rate "
                        f"({error_count}/{len(status_codes)} requests returned 4xx/5xx)."
                    ),
                    severity=_error_severity(error_rate),
                    value=round(error_rate, 4),
                    threshold=ERROR_RATE_THRESHOLD,
                    sample_size=len(status_codes),
                    recent_status_codes=status_codes[:10],
                )
            )

    return [vars(a) for a in anomalies]

"""
cluster.py — Failure clustering.

Groups all stored logs by (endpoint, status_code) so the frontend
can see which endpoint/status-code combinations are occurring most
frequently and spot patterns quickly.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from app.db import fetch_all_logs


def cluster_failures() -> list[dict[str, Any]]:
    """
    Read all logs and group them by (endpoint, status_code).

    Returns a list of incident clusters, each containing:
        - endpoint
        - status_code
        - count          : how many times this pair appeared
        - error_class    : human-readable bucket (2xx / 3xx / 4xx / 5xx)
        - latest_latency : latency of the most-recent log in this cluster
        - avg_latency    : mean latency across the cluster
        - methods        : distinct HTTP methods seen
        - first_seen     : timestamp of the oldest log in the cluster
        - last_seen      : timestamp of the newest log in the cluster

    Clusters are sorted by count descending so the noisiest problems
    appear at the top.
    """
    logs = fetch_all_logs()
    if not logs:
        return []

    # ── aggregate ──────────────────────────────────────────────────────────
    buckets: dict[tuple[str, int], dict[str, Any]] = defaultdict(
        lambda: {
            "count": 0,
            "latencies": [],
            "methods": set(),
            "timestamps": [],
        }
    )

    for log in logs:
        key = (log["endpoint"], log["status_code"])
        b = buckets[key]
        b["count"] += 1
        b["latencies"].append(log["latency"])
        b["methods"].add(log["method"])
        b["timestamps"].append(log["timestamp"])

    # ── format clusters ────────────────────────────────────────────────────
    clusters: list[dict[str, Any]] = []
    for (endpoint, status_code), b in buckets.items():
        latencies = b["latencies"]
        timestamps = sorted(b["timestamps"])

        clusters.append(
            {
                "endpoint": endpoint,
                "status_code": status_code,
                "error_class": _error_class(status_code),
                "count": b["count"],
                "avg_latency": round(sum(latencies) / len(latencies), 2),
                "latest_latency": latencies[0],   # logs are newest-first
                "methods": sorted(b["methods"]),
                "first_seen": timestamps[0] if timestamps else None,
                "last_seen": timestamps[-1] if timestamps else None,
            }
        )

    # Sort: failures first, then by count descending
    clusters.sort(key=lambda c: (c["status_code"] < 400, -c["count"]))
    return clusters


def _error_class(status_code: int) -> str:
    if status_code < 300:
        return "2xx Success"
    if status_code < 400:
        return "3xx Redirect"
    if status_code < 500:
        return "4xx Client Error"
    return "5xx Server Error"

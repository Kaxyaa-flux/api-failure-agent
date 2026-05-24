from typing import List, Dict
from datetime import datetime, timezone

# Map HTTP status codes to human-readable error classes
_ERROR_CLASS_MAP = {
    400: "Bad Request",
    401: "Unauthorized",
    403: "Forbidden",
    404: "Not Found",
    408: "Request Timeout",
    409: "Conflict",
    422: "Unprocessable Entity",
    429: "Rate Limited",
    500: "Internal Server Error",
    502: "Bad Gateway",
    503: "Service Unavailable",
    504: "Gateway Timeout",
}


def _error_class(status_code: int) -> str:
    if status_code in _ERROR_CLASS_MAP:
        return _ERROR_CLASS_MAP[status_code]
    if 400 <= status_code < 500:
        return "Client Error"
    if 500 <= status_code < 600:
        return "Server Error"
    return "Unknown"


def _parse_ts(ts_str: str) -> datetime:
    """Parse an ISO 8601 timestamp string into a UTC-aware datetime object."""
    try:
        dt = datetime.fromisoformat(ts_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        # Fallback: epoch so it never disrupts min/max comparisons
        return datetime.fromtimestamp(0, tz=timezone.utc)


def cluster_failures(logs: List[Dict]) -> List[Dict]:
    """
    Group logs by (endpoint, status_code).
    Fields per cluster:
        endpoint, status_code, error_class, count, avg_latency,
        latest_latency, methods, first_seen, last_seen
    Sorting: failures (status >= 400) first, then by count descending.
    """
    buckets: Dict[tuple, Dict] = {}

    for log in logs:
        ep = log["endpoint"]
        sc = log["status_code"]
        key = (ep, sc)

        log_dt = _parse_ts(log["timestamp"])

        if key not in buckets:
            buckets[key] = {
                "endpoint": ep,
                "status_code": sc,
                "error_class": _error_class(sc),
                "count": 0,
                "latency_sum": 0.0,
                # list of (datetime, latency) for finding latest
                "_ts_lat_pairs": [],
                "methods": set(),
                "first_seen_dt": log_dt,
                "last_seen_dt": log_dt,
                "first_seen": log["timestamp"],
                "last_seen": log["timestamp"],
            }

        b = buckets[key]
        b["count"] += 1
        b["latency_sum"] += log["latency"]
        b["_ts_lat_pairs"].append((log_dt, log["latency"]))
        b["methods"].add(log["method"])

        # Track first/last using parsed datetime objects (not string comparison)
        if log_dt < b["first_seen_dt"]:
            b["first_seen_dt"] = log_dt
            b["first_seen"] = log["timestamp"]
        if log_dt > b["last_seen_dt"]:
            b["last_seen_dt"] = log_dt
            b["last_seen"] = log["timestamp"]

    # Build final cluster objects
    clusters = []
    for b in buckets.values():
        count = b["count"]
        avg_latency = round(b["latency_sum"] / count, 2) if count else 0.0

        # Sort (datetime, latency) pairs and take the most recent latency
        sorted_pairs = sorted(b["_ts_lat_pairs"], key=lambda p: p[0])
        latest_latency = sorted_pairs[-1][1] if sorted_pairs else 0.0

        clusters.append({
            "endpoint": b["endpoint"],
            "status_code": b["status_code"],
            "error_class": b["error_class"],
            "count": count,
            "avg_latency": avg_latency,
            "latest_latency": round(latest_latency, 2),
            "methods": sorted(b["methods"]),
            "first_seen": b["first_seen"],
            "last_seen": b["last_seen"],
        })

    # Sort: failures first (status >= 400), then by count descending
    clusters.sort(key=lambda c: (0 if c["status_code"] >= 400 else 1, -c["count"]))
    return clusters

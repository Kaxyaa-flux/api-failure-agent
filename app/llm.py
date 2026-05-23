"""
llm.py — AI alert generation.

Tries to call the Anthropic Claude API when ANTHROPIC_API_KEY is set.
Falls back to a rich, deterministic mock when the key is absent or the
call fails.  Either way the caller receives the same schema:

    {
        "endpoint":    "/api/payment",
        "anomaly_type": "latency_spike",
        "issue":       "...",
        "severity":    "high",
        "confidence":  0.91,
        "root_cause":  "...",
        "steps":       ["...", "..."],
        "source":      "claude" | "mock"
    }
"""

from __future__ import annotations

import json
import os
import random
from typing import Any

# ── optional Claude import ─────────────────────────────────────────────────
try:
    import anthropic  # type: ignore

    _ANTHROPIC_AVAILABLE = True
except ImportError:
    _ANTHROPIC_AVAILABLE = False

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")


# ── mock templates ─────────────────────────────────────────────────────────

_LATENCY_TEMPLATES = [
    {
        "issue": "Severe latency spike detected — response time exceeded 2× the baseline average.",
        "root_cause": (
            "A downstream service dependency (database or third-party API) is "
            "responding slower than normal, causing queued requests to back up."
        ),
        "steps": [
            "Check database query execution times with EXPLAIN ANALYZE.",
            "Review connection-pool saturation metrics in your APM dashboard.",
            "Inspect downstream service health pages and SLA dashboards.",
            "Enable query result caching (Redis/Memcached) for hot read paths.",
            "Add circuit-breaker logic to fail fast when latency exceeds SLA.",
        ],
    },
    {
        "issue": "Response latency is more than double the rolling average — SLA at risk.",
        "root_cause": (
            "Recent deployment or configuration change may have introduced an "
            "N+1 query pattern or missing database index."
        ),
        "steps": [
            "Compare deployment timestamps with the latency spike onset.",
            "Run EXPLAIN on frequently called queries to find sequential scans.",
            "Check if a recent migration dropped or modified an index.",
            "Profile the application with py-spy or cProfile under load.",
            "Roll back the latest release as a quick mitigation if needed.",
        ],
    },
    {
        "issue": "Latency anomaly detected — tail latency (p99) is critically high.",
        "root_cause": (
            "Memory pressure or garbage-collection pauses may be stalling "
            "request processing on the application server."
        ),
        "steps": [
            "Inspect heap usage and GC pause logs on application hosts.",
            "Scale out the service horizontally to reduce per-instance load.",
            "Tune GC settings (e.g., increase heap size or switch GC strategy).",
            "Add request-timeout middleware to shed slow requests early.",
            "Evaluate moving CPU-intensive work to an async background queue.",
        ],
    },
]

_ERROR_RATE_TEMPLATES = [
    {
        "issue": "Error rate exceeded 20% threshold — more than 1 in 5 requests are failing.",
        "root_cause": (
            "Authentication or authorisation middleware may be misconfigured, "
            "causing valid requests to be rejected with 4xx responses."
        ),
        "steps": [
            "Tail the application error logs and look for the first 4xx/5xx spike.",
            "Verify JWT / API-key validation logic hasn't changed recently.",
            "Check upstream load-balancer health-check and routing rules.",
            "Run a smoke test against the affected endpoint with a valid token.",
            "Confirm environment variables (secrets, DB URIs) are correctly set.",
        ],
    },
    {
        "issue": "High 5xx error rate — server-side failures are impacting users.",
        "root_cause": (
            "Unhandled exceptions in business logic, likely due to a missing "
            "null-check or schema mismatch after a recent API contract change."
        ),
        "steps": [
            "Search Sentry / error-tracking tool for the most recent exception traces.",
            "Review recent PRs for changes to request/response schema definitions.",
            "Reproduce the failure locally with the exact payload from a failing log.",
            "Add input validation (Pydantic) to reject malformed payloads early.",
            "Deploy a hotfix and monitor error rate for the next 10 minutes.",
        ],
    },
    {
        "issue": "Sustained error storm detected — error rate is critically above threshold.",
        "root_cause": (
            "A dependent microservice is down or returning errors, and the lack "
            "of a fallback is cascading failures to this endpoint."
        ),
        "steps": [
            "Check the health of all downstream services this endpoint depends on.",
            "Implement a circuit breaker (e.g., pybreaker) to open on repeated failures.",
            "Return a cached or degraded response instead of propagating the error.",
            "Set up PagerDuty / OpsGenie alerts tied to this error rate metric.",
            "Conduct a post-mortem and add a regression test for this scenario.",
        ],
    },
]


def _pick_mock(anomaly_type: str, endpoint: str, severity: str) -> dict[str, Any]:
    templates = (
        _LATENCY_TEMPLATES
        if anomaly_type == "latency_spike"
        else _ERROR_RATE_TEMPLATES
    )
    tpl = random.choice(templates)
    confidence = round(random.uniform(0.78, 0.97), 2)

    return {
        "endpoint": endpoint,
        "anomaly_type": anomaly_type,
        "issue": tpl["issue"],
        "severity": severity,
        "confidence": confidence,
        "root_cause": tpl["root_cause"],
        "steps": tpl["steps"],
        "source": "mock",
    }


# ── Claude-powered generation ──────────────────────────────────────────────

_SYSTEM_PROMPT = (
    "You are an expert SRE and backend engineer. "
    "Given a JSON description of an API anomaly, respond ONLY with a single valid JSON object "
    "(no markdown fences) containing exactly these keys: "
    "issue (string), severity (string: low|medium|high), confidence (float 0-1), "
    "root_cause (string), steps (array of 3-5 strings). "
    "Be concise, technical, and actionable."
)


def _call_claude(anomaly: dict[str, Any]) -> dict[str, Any] | None:
    if not _ANTHROPIC_AVAILABLE or not ANTHROPIC_API_KEY:
        return None
    try:
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        user_msg = (
            f"Anomaly detected:\n"
            f"  Endpoint    : {anomaly['endpoint']}\n"
            f"  Type        : {anomaly['anomaly_type']}\n"
            f"  Description : {anomaly['description']}\n"
            f"  Severity    : {anomaly['severity']}\n"
            f"  Value       : {anomaly['value']}\n"
            f"  Threshold   : {anomaly['threshold']}\n"
            f"  Sample size : {anomaly['sample_size']} requests\n\n"
            "Generate an actionable incident alert."
        )
        message = client.messages.create(
            model="claude-opus-4-5",
            max_tokens=512,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_msg}],
        )
        raw = message.content[0].text.strip()
        parsed = json.loads(raw)

        return {
            "endpoint": anomaly["endpoint"],
            "anomaly_type": anomaly["anomaly_type"],
            "issue": parsed.get("issue", ""),
            "severity": parsed.get("severity", anomaly["severity"]),
            "confidence": float(parsed.get("confidence", 0.85)),
            "root_cause": parsed.get("root_cause", ""),
            "steps": parsed.get("steps", []),
            "source": "claude",
        }
    except Exception:
        return None


# ── public API ─────────────────────────────────────────────────────────────

def generate_alerts(anomalies: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Accept the list returned by anomaly.detect_anomalies() and return
    one alert dict per anomaly.
    """
    alerts: list[dict[str, Any]] = []
    for anomaly in anomalies:
        result = _call_claude(anomaly)
        if result is None:
            result = _pick_mock(
                anomaly_type=anomaly["anomaly_type"],
                endpoint=anomaly["endpoint"],
                severity=anomaly["severity"],
            )
        alerts.append(result)
    return alerts

import os
import json
import re
import random

try:
    import anthropic  # type: ignore
    _HAS_SDK = True
except ImportError:
    _HAS_SDK = False

MODEL = "claude-sonnet-4-20250514"
MAX_TOKENS = 1024  # Increased from 512 to prevent response truncation

# ── Singleton Anthropic client (created once, reused per request) ──────────────
_client: "anthropic.Anthropic | None" = None


def _get_client() -> "anthropic.Anthropic":
    """Return the module-level singleton Anthropic client, creating it once."""
    global _client
    if _client is None:
        api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
        if not api_key:
            raise EnvironmentError("ANTHROPIC_API_KEY is not set or is empty.")
        _client = anthropic.Anthropic(api_key=api_key)
    return _client


# ── Mock templates ─────────────────────────────────────────────────────────────

_LATENCY_MOCKS = [
    {
        "issue": "Severe latency spike detected — response time exceeded 2x baseline",
        "severity": "high",
        "confidence": 0.91,
        "root_cause": (
            "Database query plan regression after a schema migration caused full-table "
            "scans, dramatically increasing response time."
        ),
        "steps": [
            "Run EXPLAIN ANALYZE on the slowest queries for this endpoint.",
            "Check for missing or invalidated indexes post-migration.",
            "Review deployment history for recent schema changes.",
            "Consider query result caching with Redis for read-heavy paths.",
            "Set up alerting on p99 latency to catch regressions early.",
        ],
        "source": "mock",
    },
    {
        "issue": "Latency spike — downstream service dependency is responding slowly",
        "severity": "medium",
        "confidence": 0.87,
        "root_cause": (
            "A downstream microservice (e.g. auth or payment provider) is experiencing "
            "degraded performance, causing cascading latency upstream."
        ),
        "steps": [
            "Check the health dashboard of all downstream service dependencies.",
            "Inspect distributed traces to isolate the slow span.",
            "Implement circuit breakers to fail fast when a dependency is slow.",
            "Add timeouts on outbound HTTP calls to prevent thread exhaustion.",
            "Review SLA agreements with third-party providers.",
        ],
        "source": "mock",
    },
    {
        "issue": "Latency anomaly — connection pool saturation detected",
        "severity": "critical",
        "confidence": 0.95,
        "root_cause": (
            "The database connection pool is exhausted; requests are queuing waiting "
            "for an available connection, inflating latency."
        ),
        "steps": [
            "Immediately increase the connection pool size in your DB config.",
            "Audit for connection leaks — ensure all connections are released.",
            "Enable connection pool metrics in your APM tool.",
            "Consider read replicas to distribute the load.",
            "Implement request queuing with back-pressure to prevent cascading failures.",
        ],
        "source": "mock",
    },
]

_ERROR_RATE_MOCKS = [
    {
        "issue": "High error rate — more than 20% of requests are returning 5xx errors",
        "severity": "critical",
        "confidence": 0.93,
        "root_cause": (
            "An unhandled exception in the request handler is causing repeated 500 "
            "Internal Server Errors, likely triggered by a bad input or config change."
        ),
        "steps": [
            "Check application logs for stack traces around the error spike.",
            "Review recent code deployments and roll back if correlated.",
            "Add input validation and sanitization to the endpoint.",
            "Implement structured error handling with proper HTTP status codes.",
            "Set up Sentry or similar for real-time exception tracking.",
        ],
        "source": "mock",
    },
    {
        "issue": "Elevated 4xx error rate — clients are sending malformed requests",
        "severity": "medium",
        "confidence": 0.88,
        "root_cause": (
            "A breaking API change or missing documentation is causing clients to send "
            "requests with incorrect parameters or missing required fields."
        ),
        "steps": [
            "Review recent API contract changes that may have broken clients.",
            "Add detailed error messages to 4xx responses to aid client debugging.",
            "Publish a changelog and notify API consumers of breaking changes.",
            "Implement versioning (e.g. /v2/) to avoid breaking existing integrations.",
            "Add request validation middleware with clear error descriptions.",
        ],
        "source": "mock",
    },
    {
        "issue": "Service returning 503 errors — resource limits exceeded",
        "severity": "high",
        "confidence": 0.89,
        "root_cause": (
            "The service is under unexpected load and hitting CPU or memory limits, "
            "causing the load balancer to return 503 Service Unavailable responses."
        ),
        "steps": [
            "Check infrastructure metrics: CPU, memory, and request queue depth.",
            "Scale out the service horizontally by adding more instances.",
            "Enable auto-scaling policies based on CPU/request rate thresholds.",
            "Implement rate limiting to protect the service from traffic spikes.",
            "Profile the service for memory leaks or CPU-intensive operations.",
        ],
        "source": "mock",
    },
]


def _pick_mock(anomaly: dict) -> dict:
    """Return a rich mock alert based on the anomaly type."""
    if anomaly.get("anomaly_type") == "latency_spike":
        return dict(random.choice(_LATENCY_MOCKS))
    return dict(random.choice(_ERROR_RATE_MOCKS))


# ── Claude integration ─────────────────────────────────────────────────────────

def _build_prompt(anomaly: dict) -> str:
    return (
        "You are an expert SRE analysing an API anomaly. "
        "Return ONLY a valid JSON object (no markdown fences) with these exact keys:\n"
        "  endpoint (string), anomaly_type (string), issue (string), "
        "severity (string: low/medium/high/critical), confidence (float 0-1), "
        "root_cause (string), steps (array of strings), source (must be \"claude\").\n\n"
        f"Anomaly data:\n{json.dumps(anomaly, indent=2)}"
    )


def _strip_markdown_fences(text: str) -> str:
    """Remove ```json ... ``` or ``` ... ``` wrappers Claude sometimes adds."""
    text = text.strip()
    # Remove opening fence (```json or ```)
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    # Remove closing fence
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def generate_alert(anomaly: dict) -> dict:
    """
    Generate a structured alert for the given anomaly.
    Returns a dict with: endpoint, anomaly_type, issue, severity,
                         confidence, root_cause, steps, source.
    No `timestamp` field is included.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()

    if api_key and _HAS_SDK:
        try:
            client = _get_client()
            message = client.messages.create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                messages=[{"role": "user", "content": _build_prompt(anomaly)}],
            )
            text = message.content[0].text.strip()
            # Log raw output before parsing so failures are visible (#12)
            print(f"[llm] Claude raw response: {text[:300]}")
            text = _strip_markdown_fences(text)
            result = json.loads(text)
            # Ensure required fields and correct source tag
            result["source"] = "claude"
            result.setdefault("endpoint", anomaly.get("endpoint", ""))
            result.setdefault("anomaly_type", anomaly.get("anomaly_type", ""))
            # Remove any timestamp if Claude sneaked one in
            result.pop("timestamp", None)
            return result

        except EnvironmentError as exc:
            # Missing API key — log clearly, do not mask
            print(f"[llm] Configuration error: {exc} — using mock fallback")

        except anthropic.AuthenticationError as exc:  # type: ignore[attr-defined]
            print(f"[llm] Authentication error (invalid API key): {exc} — using mock fallback")

        except anthropic.RateLimitError as exc:  # type: ignore[attr-defined]
            print(f"[llm] Rate limit exceeded: {exc} — using mock fallback")

        except anthropic.APIConnectionError as exc:  # type: ignore[attr-defined]
            print(f"[llm] Network/connection error reaching Anthropic API: {exc} — using mock fallback")

        except json.JSONDecodeError as exc:
            print(f"[llm] Failed to parse Claude JSON response: {exc} — using mock fallback")

        except Exception as exc:
            # Catch-all for unexpected errors — still logged, not silently masked
            print(f"[llm] Unexpected error during Claude call: {type(exc).__name__}: {exc} — using mock fallback")

    # Rich mock fallback
    mock = _pick_mock(anomaly)
    mock["endpoint"] = anomaly.get("endpoint", "unknown")
    mock["anomaly_type"] = anomaly.get("anomaly_type", "unknown")
    mock.pop("timestamp", None)
    return mock

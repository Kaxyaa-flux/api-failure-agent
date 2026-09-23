import os
import json
import re
import random

try:
    import groq  # type: ignore
    _HAS_SDK = True
except ImportError:
    _HAS_SDK = False

MODEL = "openai/gpt-oss-120b"
MAX_TOKENS = 1024  # Increased from 512 to prevent response truncation

# ── Deployment context ──────────────────────────────────────────────────────
# Injected into every prompt so the model reasons from your ACTUAL
# infrastructure instead of guessing generic SRE causes (e.g. "CPU limits",
# "DB query plan regression") that may not apply to your stack at all.
# Edit this to match your real deployment.
DEPLOYMENT_CONTEXT = os.environ.get(
    "DEPLOYMENT_CONTEXT",
    "Hosted on Vercel serverless functions with a 10-second execution "
    "timeout per request — a request that takes longer than 10s is killed "
    "by the platform and returns 503. This is a TIMEOUT, not a CPU or "
    "memory limit. Database is Supabase Postgres, accessed via the pg8000 "
    "driver through the IPv4 connection pooler (port 6543) — if this URL "
    "is misconfigured (e.g. pointing at the old IPv6/5432 endpoint), "
    "connections hang until the platform times out the whole request. "
    "LLM calls go to Groq's API. Air quality data comes from OpenWeatherMap.",
)

# Per-endpoint description of what each route actually does, so the model
# doesn't assume generic backend behavior (e.g. a DB call) that isn't there.
# Extend this dict as you add routes.
ENDPOINT_CONTEXT = {
    "/api/aqi": "Calls OpenWeatherMap's geocoding + air-pollution APIs only. No database access, no LLM call.",
    "/api/chat": "Calls OpenWeatherMap for AQI data, then calls the Groq LLM API, then writes one row to the ChatHistory table (Postgres via Supabase pooler) if a username was given. A hang in any of these three steps — OpenWeatherMap, Groq, or the DB pooler — can cause the 10s serverless timeout.",
    "/api/auth/register": "Writes one row to the User table (Postgres via Supabase pooler). No external API calls.",
    "/api/auth/login": "Reads one row from the User table (Postgres via Supabase pooler). No external API calls.",
    "/api/auth/salt": "Reads one row from the User table (Postgres via Supabase pooler). No external API calls.",
    "/api/history": "Reads or writes ChatHistory rows (Postgres via Supabase pooler). No external API calls.",
    "/api/validate-keys": "Calls OpenWeatherMap and Groq once each to test provided keys. No database access.",
}

# ── Singleton Groq client (created once, reused per request) ──────────────
_client: "groq.Groq | None" = None


def _get_client() -> "groq.Groq":
    """Return the module-level singleton Groq client, creating it once."""
    global _client
    if _client is None:
        api_key = os.environ.get("GROQ_API_KEY", "").strip()
        if not api_key:
            raise EnvironmentError("GROQ_API_KEY is not set or is empty.")
        _client = groq.Groq(api_key=api_key)
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
    endpoint = anomaly.get("endpoint", "")
    endpoint_note = ENDPOINT_CONTEXT.get(endpoint)

    context = f"Deployment context: {DEPLOYMENT_CONTEXT}"
    if endpoint_note:
        context += f"\n\nWhat this specific endpoint does: {endpoint_note}"
    else:
        context += (
            "\n\nNo specific description is available for this endpoint's "
            "internals — do not guess what subsystems (database, cache, "
            "external APIs) it touches."
        )

    return (
        "You are an expert SRE analysing an API anomaly. "
        "Ground root_cause and steps ONLY in the deployment context and "
        "endpoint description below. Do NOT invent a specific cause (database "
        "query plans, CPU/memory limits, cache issues, etc.) unless the context "
        "explicitly supports it — if the endpoint description says there's no "
        "database call, do not suggest database fixes. If the real cause isn't "
        "determinable from what's given, say so generically and lower the "
        "confidence score rather than naming an unsupported specific cause.\n\n"
        f"{context}\n\n"
        "Return ONLY a valid JSON object (no markdown fences) with these exact keys:\n"
        "  endpoint (string), anomaly_type (string), issue (string), "
        "severity (string: low/medium/high/critical), confidence (float 0-1), "
        "root_cause (string), steps (array of strings), source (must be \"groq\").\n\n"
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
    api_key = os.environ.get("GROQ_API_KEY", "").strip()

    if api_key and _HAS_SDK:
        try:
            client = _get_client()
            completion = client.chat.completions.create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                messages=[{"role": "user", "content": _build_prompt(anomaly)}],
            )
            text = completion.choices[0].message.content.strip()
            # Log raw output before parsing so failures are visible (#12)
            print(f"[llm] Groq raw response: {text[:300]}")
            text = _strip_markdown_fences(text)
            result = json.loads(text)
            # Ensure required fields and correct source tag
            result["source"] = "groq"
            result.setdefault("endpoint", anomaly.get("endpoint", ""))
            result.setdefault("anomaly_type", anomaly.get("anomaly_type", ""))
            # Remove any timestamp if Groq sneaked one in
            result.pop("timestamp", None)
            return result

        except EnvironmentError as exc:
            # Missing API key — log clearly, do not mask
            print(f"[llm] Configuration error: {exc} — using mock fallback")

        except groq.AuthenticationError as exc:  # type: ignore[attr-defined]
            print(f"[llm] Authentication error (invalid API key): {exc} — using mock fallback")

        except groq.RateLimitError as exc:  # type: ignore[attr-defined]
            print(f"[llm] Rate limit exceeded: {exc} — using mock fallback")

        except groq.APIConnectionError as exc:  # type: ignore[attr-defined]
            print(f"[llm] Network/connection error reaching Groq API: {exc} — using mock fallback")

        except json.JSONDecodeError as exc:
            print(f"[llm] Failed to parse Groq JSON response: {exc} — using mock fallback")

        except Exception as exc:
            # Catch-all for unexpected errors — still logged, not silently masked
            print(f"[llm] Unexpected error during Groq call: {type(exc).__name__}: {exc} — using mock fallback")

    # Rich mock fallback
    mock = _pick_mock(anomaly)
    mock["endpoint"] = anomaly.get("endpoint", "unknown")
    mock["anomaly_type"] = anomaly.get("anomaly_type", "unknown")
    mock.pop("timestamp", None)
    return mock

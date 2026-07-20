from __future__ import annotations

import os
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from uuid import uuid4

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response


@dataclass
class RequestMetric:
    count: int = 0
    errors: int = 0
    total_seconds: float = 0.0


class MetricsRegistry:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._metrics: dict[tuple[str, str, int], RequestMetric] = defaultdict(RequestMetric)
        self.started_at = time.time()

    def record(self, method: str, path: str, status: int, elapsed: float) -> None:
        safe_path = normalise_path(path)
        with self._lock:
            metric = self._metrics[(method, safe_path, status)]
            metric.count += 1
            metric.total_seconds += elapsed
            if status >= 500:
                metric.errors += 1

    def snapshot(self) -> dict[tuple[str, str, int], RequestMetric]:
        with self._lock:
            return {key: RequestMetric(value.count, value.errors, value.total_seconds) for key, value in self._metrics.items()}


METRICS = MetricsRegistry()
_RATE_LOCK = threading.Lock()
_RATE_BUCKETS: dict[str, deque[float]] = defaultdict(deque)


def env_bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def normalise_path(path: str) -> str:
    parts = []
    for part in path.split("/"):
        if not part:
            continue
        if len(part) > 20 and ("-" in part or part.isdigit()):
            parts.append(":ref")
        else:
            parts.append(part)
    return "/" + "/".join(parts)


def _rate_limited(request: Request) -> bool:
    if not env_bool("RATE_LIMIT_ENABLED", False):
        return False
    limit = max(10, int(os.getenv("RATE_LIMIT_REQUESTS_PER_MINUTE", "240")))
    now = time.time()
    subject = getattr(getattr(request.state, "auth", None), "subject", None)
    forwarded = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    client = forwarded or (request.client.host if request.client else "unknown")
    key = f"{subject or client}:{normalise_path(request.url.path)}"
    with _RATE_LOCK:
        bucket = _RATE_BUCKETS[key]
        while bucket and bucket[0] < now - 60:
            bucket.popleft()
        if len(bucket) >= limit:
            return True
        bucket.append(now)
    return False


class ProductionProtectionMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get("x-request-id") or f"req-{uuid4().hex}"
        request.state.request_id = request_id
        started = time.perf_counter()
        if _rate_limited(request):
            response: Response = JSONResponse(status_code=429, content={"detail": "request rate limit exceeded", "requestId": request_id})
        else:
            try:
                response = await call_next(request)
            except Exception:
                elapsed = time.perf_counter() - started
                METRICS.record(request.method, request.url.path, 500, elapsed)
                raise
        elapsed = time.perf_counter() - started
        METRICS.record(request.method, request.url.path, response.status_code, elapsed)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=(), payment=(), usb=()"
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        if env_bool("SECURITY_HEADERS_ENABLED", True):
            response.headers["Content-Security-Policy"] = os.getenv(
                "CONTENT_SECURITY_POLICY",
                "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; connect-src 'self' https: wss:; frame-ancestors 'none'; base-uri 'self'; form-action 'self'",
            )
            if os.getenv("DEPLOYMENT_ENVIRONMENT", "development").lower() in {"production", "staging"}:
                response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response

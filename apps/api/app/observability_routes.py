from __future__ import annotations

import hmac
import os
import time
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import PlainTextResponse
from sqlalchemy import inspect, text
from sqlmodel import Session

from app.database import get_session
from app.production_middleware import METRICS

router = APIRouter(prefix="/api", tags=["observability"])


@router.get("/health/live")
def live() -> dict[str, Any]:
    return {
        "status": "live",
        "service": "lucyworks-api",
        "environment": os.getenv("DEPLOYMENT_ENVIRONMENT", "development"),
        "uptimeSeconds": round(time.time() - METRICS.started_at, 3),
    }


@router.get("/health/ready")
def ready(session: Session = Depends(get_session)) -> dict[str, Any]:
    checks: dict[str, Any] = {}
    try:
        session.exec(text("select 1")).first()
        checks["database"] = "ready"
    except Exception as exc:
        checks["database"] = f"failed: {type(exc).__name__}"
    try:
        tables = set(inspect(session.get_bind()).get_table_names())
        required = {"evidenceevent", "operationalblock", "canonicalepisodestate", "readinesscontrol", "pilotrun"}
        missing = sorted(required - tables)
        checks["schema"] = "ready" if not missing else {"missing": missing}
    except Exception as exc:
        checks["schema"] = f"failed: {type(exc).__name__}"
    ready_state = checks.get("database") == "ready" and checks.get("schema") == "ready"
    if not ready_state:
        raise HTTPException(status_code=503, detail={"status": "not_ready", "checks": checks})
    return {"status": "ready", "checks": checks}


def require_metrics_key(supplied: str | None) -> None:
    expected = os.getenv("METRICS_API_KEY", "")
    if not expected:
        raise HTTPException(status_code=503, detail="metrics scraping key is not configured")
    if not supplied or not hmac.compare_digest(supplied, expected):
        raise HTTPException(status_code=401, detail="valid metrics scraping key required")


@router.get("/metrics", response_class=PlainTextResponse)
def metrics(x_lucyworks_metrics_key: str | None = Header(default=None)) -> str:
    require_metrics_key(x_lucyworks_metrics_key)
    lines = [
        "# HELP lucyworks_process_uptime_seconds Seconds since API process start.",
        "# TYPE lucyworks_process_uptime_seconds gauge",
        f"lucyworks_process_uptime_seconds {time.time() - METRICS.started_at:.6f}",
        "# HELP lucyworks_http_requests_total Total HTTP requests.",
        "# TYPE lucyworks_http_requests_total counter",
        "# HELP lucyworks_http_request_duration_seconds_total Total request duration in seconds.",
        "# TYPE lucyworks_http_request_duration_seconds_total counter",
        "# HELP lucyworks_http_server_errors_total Total HTTP 5xx responses.",
        "# TYPE lucyworks_http_server_errors_total counter",
    ]
    for (method, path, status), metric in sorted(METRICS.snapshot().items()):
        labels = f'method="{method}",path="{path}",status="{status}"'
        lines.append(f"lucyworks_http_requests_total{{{labels}}} {metric.count}")
        lines.append(f"lucyworks_http_request_duration_seconds_total{{{labels}}} {metric.total_seconds:.6f}")
        lines.append(f"lucyworks_http_server_errors_total{{{labels}}} {metric.errors}")
    return "\n".join(lines) + "\n"

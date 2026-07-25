from __future__ import annotations

import os
from typing import Any

from starlette.responses import JSONResponse

RETIRED_WRITES = {
    "/api/shadow-mode/import-rows": "/api/v7/shadow/comparisons",
    "/api/shadow-mode/validate": "/api/v7/shadow/comparisons",
    "/api/shadow-mode/approve": "/api/v7/shadow/comparisons/{comparison_ref}",
    "/api/shadow-mode/reject": "/api/v7/shadow/comparisons/{comparison_ref}",
    "/api/realtime/publish": "/api/v7/events",
    "/api/clinical-execution/medication-orders": "/api/v8/episodes/{episode_ref}/medication-orders",
    "/api/clinical-execution/anaesthesia": "/api/clinical-execution/governed/anaesthesia",
}
RETIRED_PREFIX_WRITES = {
    ("PATCH", "/api/clinical-execution/discharge-plans/"): "/api/clinical-execution/governed/discharge-plans/{plan_ref}",
}
RETIRED_READ_PREFIXES = {
    "/api/shadow-mode": "/api/v7/shadow",
    "/api/realtime": "/api/v7/events",
}


def retirement_enabled() -> bool:
    explicit = os.getenv("LEGACY_WRITE_MODE", "").lower().strip()
    if explicit:
        return explicit == "block"
    return os.getenv("DEPLOYMENT_ENVIRONMENT", "development").lower() in {"staging", "production"}


def replacement_for(method: str, path: str) -> str | None:
    exact = RETIRED_WRITES.get(path)
    if exact:
        return exact
    for (candidate_method, prefix), replacement in RETIRED_PREFIX_WRITES.items():
        if method == candidate_method and path.startswith(prefix):
            return replacement
    return None


class LegacyWriteRetirementMiddleware:
    def __init__(self, app: Any):
        self.app = app

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return
        path = str(scope.get("path") or "")
        method = str(scope.get("method") or "GET").upper()
        replacement = replacement_for(method, path)
        if retirement_enabled() and method in {"POST", "PUT", "PATCH", "DELETE"} and replacement:
            response = JSONResponse(
                {
                    "detail": "legacy write route retired",
                    "replacement": replacement,
                    "reason": "verified identity, versioning and canonical evidence are required",
                },
                status_code=410,
                headers={"Deprecation": "true", "Link": f'<{replacement}>; rel="successor-version"'},
            )
            await response(scope, receive, send)
            return

        async def send_with_deprecation(message: dict[str, Any]) -> None:
            if message.get("type") == "http.response.start":
                for prefix, successor in RETIRED_READ_PREFIXES.items():
                    if path.startswith(prefix):
                        headers = list(message.get("headers") or [])
                        headers.extend([
                            (b"deprecation", b"true"),
                            (b"link", f'<{successor}>; rel="successor-version"'.encode("utf-8")),
                        ])
                        message["headers"] = headers
                        break
            await send(message)

        await self.app(scope, receive, send_with_deprecation)

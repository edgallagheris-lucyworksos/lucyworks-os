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


class LegacyWriteRetirementMiddleware:
    def __init__(self, app: Any):
        self.app = app

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return
        path = str(scope.get("path") or "")
        method = str(scope.get("method") or "GET").upper()
        replacement = RETIRED_WRITES.get(path)
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

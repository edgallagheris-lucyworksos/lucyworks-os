from __future__ import annotations

import re

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse


LEGACY_ESTIMATE_WRITE = re.compile(r"^/api/v8/episodes/([^/]+)/estimates$")


class RegulatedWorkflowV32BoundaryMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method.upper() == "POST":
            match = LEGACY_ESTIMATE_WRITE.match(request.url.path)
            if match:
                episode_ref = match.group(1)
                return JSONResponse(
                    status_code=410,
                    content={
                        "detail": "Legacy estimate writes are retired; use the regulated v32 estimate workflow.",
                        "replacement": f"/api/v32/episodes/{episode_ref}/estimates",
                    },
                )
        return await call_next(request)

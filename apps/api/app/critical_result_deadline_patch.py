from __future__ import annotations

from app import control_plane_routes as routes
from app.critical_result_deadline_routes import router as deadline_router

# FastAPI resolves equal paths in insertion order. Put the deadline-aware reads
# before the legacy read handlers while leaving existing write routes intact.
routes.router.routes[0:0] = list(deadline_router.routes)

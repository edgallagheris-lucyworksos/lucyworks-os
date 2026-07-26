from __future__ import annotations

from typing import Any

from app import referral_identity_v12_routes as routes
from app.hospital_ops_models import OperationalBlock
from app.referral_identity_v12_datetime_routes import router as datetime_router


_canonical_block_dict = routes.block_dict


def browser_compatible_block_dict(row: OperationalBlock) -> dict[str, Any]:
    """Keep canonical camelCase while supporting the initial v12 browser message fields."""
    payload = _canonical_block_dict(row)
    payload.update({
        "area_ref": payload.get("areaRef"),
        "area_name": payload.get("areaName"),
        "starts_at": payload.get("startsAt"),
        "ends_at": payload.get("endsAt"),
    })
    return payload


routes.block_dict = browser_compatible_block_dict

# FastAPI resolves matching paths in insertion order. Put the UTC-safe read
# endpoints before the original v12 handlers so SQLite and PostgreSQL expose
# identical deadline semantics while retaining the existing write routes.
routes.router.routes[0:0] = list(datetime_router.routes)

from __future__ import annotations

from typing import Any

from app import referral_identity_v12_routes as routes
from app.hospital_ops_models import OperationalBlock


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

from __future__ import annotations

from typing import Any

from sqlalchemy import inspect as sa_inspect

from app import speech_capture_v19_routes as routes


def safe_row_dict(row: Any) -> dict[str, Any]:
    if row is None:
        return {}
    data = row.model_dump(mode="json")
    if data:
        return data
    state = sa_inspect(row)
    result: dict[str, Any] = {}
    for attribute in state.mapper.column_attrs:
        value = getattr(row, attribute.key)
        if hasattr(value, "isoformat"):
            value = value.isoformat()
        result[attribute.key] = value
    return result


routes.row_dict = safe_row_dict

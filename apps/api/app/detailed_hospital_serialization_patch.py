from __future__ import annotations

from typing import Any

from sqlalchemy import inspect as sqlalchemy_inspect

from app import detailed_hospital_completion_routes as completion_routes


def robust_row_dict(row: Any) -> dict[str, Any]:
    if row is None:
        return {}
    dumped = row.model_dump(mode="json")
    if dumped:
        return dumped
    # SQLAlchemy expires ORM attributes after commit. SQLModel's model_dump can
    # consequently return an empty mapping until an attribute is accessed. Read
    # each mapped column through the ORM so the attached session refreshes the
    # row, then serialise through Pydantic again for datetime/JSON consistency.
    state = sqlalchemy_inspect(row)
    for attribute in state.mapper.column_attrs:
        getattr(row, attribute.key)
    return row.model_dump(mode="json")


completion_routes.row_dict = robust_row_dict

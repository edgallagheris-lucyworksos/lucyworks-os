from __future__ import annotations

from sqlalchemy.exc import IntegrityError
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.main_fixed import app


@app.exception_handler(IntegrityError)
async def database_integrity_error(_request: Request, _exc: IntegrityError) -> JSONResponse:
    """Do not expose database details or turn duplicate commands into 500s."""

    return JSONResponse(
        status_code=409,
        content={
            "detail": {
                "code": "database_integrity_conflict",
                "message": "The stable reference or idempotency key already exists. Refresh the current record instead of repeating the write.",
            }
        },
    )

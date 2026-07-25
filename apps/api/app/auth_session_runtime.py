from __future__ import annotations

import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone
from http.cookies import SimpleCookie
from typing import Any
from uuid import uuid4

from fastapi import HTTPException, Response
from sqlmodel import Session, select

from app.database import engine
from app.v7_models import AuthSession

SESSION_COOKIE = "lucyworks_session"
CSRF_COOKIE = "lucyworks_csrf"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def cookie_secure() -> bool:
    return os.getenv("DEPLOYMENT_ENVIRONMENT", "development").lower() in {"staging", "production"}


def session_lifetime() -> tuple[timedelta, timedelta]:
    absolute = timedelta(minutes=max(15, int(os.getenv("AUTH_SESSION_MINUTES", "480"))))
    idle = timedelta(minutes=max(5, int(os.getenv("AUTH_IDLE_MINUTES", "30"))))
    return absolute, idle


def issue_browser_session(session: Session, response: Response, auth: Any) -> dict[str, Any]:
    now = utc_now()
    absolute, idle = session_lifetime()
    token = secrets.token_urlsafe(48)
    csrf = secrets.token_urlsafe(32)
    row = AuthSession(
        session_ref=f"session-{uuid4().hex}",
        token_hash=digest(token),
        csrf_hash=digest(csrf),
        subject=auth.subject,
        actor_id=str(auth.actor_id or auth.subject),
        actor_name=auth.actor_name,
        actor_role=auth.role,
        email=auth.email,
        issuer=auth.issuer,
        auth_source=f"{auth.auth_source}:server_session",
        claims=dict(auth.claims or {}),
        expires_at=now + absolute,
        idle_expires_at=now + idle,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    secure = cookie_secure()
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=int(absolute.total_seconds()),
        httponly=True,
        secure=secure,
        samesite="lax",
        path="/",
    )
    response.set_cookie(
        CSRF_COOKIE,
        csrf,
        max_age=int(absolute.total_seconds()),
        httponly=False,
        secure=secure,
        samesite="strict",
        path="/",
    )
    return {"sessionRef": row.session_ref, "csrfToken": csrf, "expiresAt": row.expires_at.isoformat()}


def _cookie_value(cookie_header: str, name: str) -> str | None:
    if not cookie_header:
        return None
    parsed = SimpleCookie()
    try:
        parsed.load(cookie_header)
    except Exception:
        return None
    morsel = parsed.get(name)
    return morsel.value if morsel else None


def resolve_cookie_auth(cookie_header: str, csrf_header: str | None, method: str) -> Any | None:
    raw = _cookie_value(cookie_header, SESSION_COOKIE)
    if not raw:
        return None
    now = utc_now()
    with Session(engine) as session:
        row = session.exec(select(AuthSession).where(AuthSession.token_hash == digest(raw))).first()
        if not row or row.revoked_at:
            raise HTTPException(status_code=401, detail="browser session is invalid or revoked")
        if aware(row.expires_at) <= now or aware(row.idle_expires_at) <= now:
            row.revoked_at = now
            row.revoked_reason = "expired"
            session.add(row)
            session.commit()
            raise HTTPException(status_code=401, detail="browser session expired")
        if method.upper() in {"POST", "PUT", "PATCH", "DELETE"}:
            if not csrf_header or not secrets.compare_digest(digest(csrf_header), row.csrf_hash):
                raise HTTPException(status_code=403, detail="CSRF token is missing or invalid")
        _, idle = session_lifetime()
        row.last_seen_at = now
        row.idle_expires_at = min(aware(row.expires_at), now + idle)
        session.add(row)
        session.commit()
        from app.auth import AuthContext

        return AuthContext(
            subject=row.subject,
            actor_id=row.actor_id,
            actor_name=row.actor_name,
            role=row.actor_role,
            email=row.email,
            issuer=row.issuer,
            auth_source=row.auth_source,
            verified=True,
            expires_at=aware(row.expires_at),
            claims=dict(row.claims or {}),
        )


def revoke_browser_session(session: Session, cookie_header: str, reason: str = "logout") -> None:
    raw = _cookie_value(cookie_header, SESSION_COOKIE)
    if not raw:
        return
    row = session.exec(select(AuthSession).where(AuthSession.token_hash == digest(raw))).first()
    if row and not row.revoked_at:
        row.revoked_at = utc_now()
        row.revoked_reason = reason
        session.add(row)
        session.commit()


def clear_browser_session(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE, path="/")
    response.delete_cookie(CSRF_COOKIE, path="/")

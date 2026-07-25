from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel
from sqlmodel import Session, select

from app.auth import (
    AuthContext,
    auth_enforcement,
    auth_mode,
    decode_access_token,
    dev_login_enabled,
    issue_local_token,
    require_authenticated,
)
from app.auth_session_runtime import clear_browser_session, issue_browser_session, revoke_browser_session
from app.database import get_session
from app.models import User
from app.v7_models import AuthSession

router = APIRouter(prefix="/api/auth", tags=["authentication"])


def setting(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def user_payload(auth: AuthContext) -> dict[str, Any]:
    return {
        "id": auth.actor_id,
        "subject": auth.subject,
        "name": auth.actor_name,
        "role": auth.role,
        "email": auth.email,
        "issuer": auth.issuer,
        "authSource": auth.auth_source,
        "verified": auth.verified,
        "expiresAt": auth.expires_at.isoformat() if auth.expires_at else None,
    }


class DevLoginRequest(BaseModel):
    user_id: int


class OIDCExchangeRequest(BaseModel):
    code: str
    code_verifier: str
    redirect_uri: str


class StepUpRequest(BaseModel):
    reauthentication_token: str
    reason: str


@router.get("/config")
def authentication_config() -> dict[str, Any]:
    mode = auth_mode()
    return {
        "mode": mode,
        "enforcement": auth_enforcement(),
        "sessionMode": "secure_cookie",
        "devLoginEnabled": mode == "local" and dev_login_enabled(),
        "oidc": {
            "authorizationUrl": setting("OIDC_AUTHORIZATION_URL") or None,
            "clientId": setting("OIDC_CLIENT_ID") or None,
            "audience": setting("AUTH_AUDIENCE", "lucyworks-api") or None,
            "scope": setting("OIDC_SCOPE", "openid profile email") or None,
        } if mode == "oidc" else None,
    }


@router.get("/dev-users")
def development_users(session: Session = Depends(get_session)) -> list[dict[str, Any]]:
    if auth_mode() != "local" or not dev_login_enabled():
        raise HTTPException(status_code=404, detail="development login is disabled")
    rows = session.exec(select(User).where(User.active == True).order_by(User.name)).all()  # noqa: E712
    return [{"id": row.id, "name": row.name, "role": row.role, "email": row.email} for row in rows]


def login_response(session: Session, response: Response, auth: AuthContext, bearer_token: str | None = None, expires_in: int | None = None) -> dict[str, Any]:
    browser = issue_browser_session(session, response, auth)
    payload: dict[str, Any] = {"user": user_payload(auth), "session": browser, "tokenType": "Cookie"}
    default_bearer = "true" if auth_mode() == "local" else "false"
    if setting("AUTH_RETURN_BEARER_DEV", default_bearer).lower() in {"1", "true", "yes"} and bearer_token:
        payload.update({"accessToken": bearer_token, "expiresIn": expires_in, "tokenType": "Bearer"})
    return payload


@router.post("/dev-login")
def development_login(payload: DevLoginRequest, response: Response, session: Session = Depends(get_session)) -> dict[str, Any]:
    if auth_mode() != "local" or not dev_login_enabled():
        raise HTTPException(status_code=404, detail="development login is disabled")
    user = session.get(User, payload.user_id)
    if not user or not user.active:
        raise HTTPException(status_code=404, detail="active user not found")
    token, expires_in = issue_local_token(user_id=user.id or payload.user_id, name=user.name, role=user.role, email=user.email)
    verified = decode_access_token(token)
    return login_response(session, response, verified, token, expires_in)


@router.post("/oidc/exchange")
async def oidc_exchange(payload: OIDCExchangeRequest, response: Response, session: Session = Depends(get_session)) -> dict[str, Any]:
    if auth_mode() != "oidc":
        raise HTTPException(status_code=404, detail="OIDC authentication is not enabled")
    token_url = setting("OIDC_TOKEN_URL")
    client_id = setting("OIDC_CLIENT_ID")
    if not token_url or not client_id:
        raise HTTPException(status_code=503, detail="OIDC token exchange is not configured")
    form = {"grant_type": "authorization_code", "client_id": client_id, "code": payload.code, "code_verifier": payload.code_verifier, "redirect_uri": payload.redirect_uri}
    client_secret = setting("OIDC_CLIENT_SECRET")
    if client_secret:
        form["client_secret"] = client_secret
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            provider_response = await client.post(token_url, data=form, headers={"Accept": "application/json"})
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="OIDC provider could not be reached") from exc
    if provider_response.status_code >= 400:
        raise HTTPException(status_code=401, detail="OIDC code exchange failed")
    data = provider_response.json()
    access_token = data.get("access_token")
    if not access_token:
        raise HTTPException(status_code=401, detail="OIDC provider did not return an access token")
    verified = decode_access_token(str(access_token))
    return login_response(session, response, verified, str(access_token), data.get("expires_in"))


@router.get("/me")
def current_identity(auth: AuthContext = Depends(require_authenticated)) -> dict[str, Any]:
    return {"user": user_payload(auth)}


@router.post("/step-up")
def step_up(payload: StepUpRequest, request: Request, session: Session = Depends(get_session), auth: AuthContext = Depends(require_authenticated)) -> dict[str, Any]:
    fresh = decode_access_token(payload.reauthentication_token)
    if fresh.subject != auth.subject:
        raise HTTPException(status_code=403, detail="step-up identity does not match the active session")
    cookie_header = request.headers.get("cookie", "")
    from app.auth_session_runtime import SESSION_COOKIE, _cookie_value, digest
    raw = _cookie_value(cookie_header, SESSION_COOKIE)
    if not raw:
        raise HTTPException(status_code=400, detail="step-up requires a browser session")
    row = session.exec(select(AuthSession).where(AuthSession.token_hash == digest(raw))).first()
    if not row or row.revoked_at:
        raise HTTPException(status_code=401, detail="browser session is invalid")
    row.step_up_until = datetime.now(timezone.utc) + timedelta(minutes=10)
    session.add(row)
    session.commit()
    return {"ok": True, "stepUpUntil": row.step_up_until.isoformat(), "reason": payload.reason}


@router.post("/logout")
def logout(request: Request, response: Response, session: Session = Depends(get_session), auth: AuthContext = Depends(require_authenticated)) -> dict[str, Any]:
    revoke_browser_session(session, request.headers.get("cookie", ""), "logout")
    clear_browser_session(response)
    return {"ok": True, "subject": auth.subject}


@router.post("/revoke-all")
def revoke_all_sessions(session: Session = Depends(get_session), auth: AuthContext = Depends(require_authenticated)) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    rows = session.exec(select(AuthSession).where(AuthSession.subject == auth.subject, AuthSession.revoked_at == None)).all()  # noqa: E711
    for row in rows:
        row.revoked_at = now
        row.revoked_reason = "user_revoke_all"
        session.add(row)
    session.commit()
    return {"ok": True, "revoked": len(rows)}

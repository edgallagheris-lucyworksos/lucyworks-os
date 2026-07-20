from __future__ import annotations

import os
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
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
from app.database import get_session
from app.models import User

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


@router.get("/config")
def authentication_config() -> dict[str, Any]:
    mode = auth_mode()
    return {
        "mode": mode,
        "enforcement": auth_enforcement(),
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


@router.post("/dev-login")
def development_login(payload: DevLoginRequest, session: Session = Depends(get_session)) -> dict[str, Any]:
    if auth_mode() != "local" or not dev_login_enabled():
        raise HTTPException(status_code=404, detail="development login is disabled")
    user = session.get(User, payload.user_id)
    if not user or not user.active:
        raise HTTPException(status_code=404, detail="active user not found")
    token, expires_in = issue_local_token(
        user_id=user.id or payload.user_id,
        name=user.name,
        role=user.role,
        email=user.email,
    )
    verified = decode_access_token(token)
    return {"accessToken": token, "tokenType": "Bearer", "expiresIn": expires_in, "user": user_payload(verified)}


@router.post("/oidc/exchange")
async def oidc_exchange(payload: OIDCExchangeRequest) -> dict[str, Any]:
    if auth_mode() != "oidc":
        raise HTTPException(status_code=404, detail="OIDC authentication is not enabled")
    token_url = setting("OIDC_TOKEN_URL")
    client_id = setting("OIDC_CLIENT_ID")
    if not token_url or not client_id:
        raise HTTPException(status_code=503, detail="OIDC token exchange is not configured")

    form = {
        "grant_type": "authorization_code",
        "client_id": client_id,
        "code": payload.code,
        "code_verifier": payload.code_verifier,
        "redirect_uri": payload.redirect_uri,
    }
    client_secret = setting("OIDC_CLIENT_SECRET")
    if client_secret:
        form["client_secret"] = client_secret

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(token_url, data=form, headers={"Accept": "application/json"})
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="OIDC provider could not be reached") from exc
    if response.status_code >= 400:
        raise HTTPException(status_code=401, detail="OIDC code exchange failed")
    data = response.json()
    access_token = data.get("access_token")
    if not access_token:
        raise HTTPException(status_code=401, detail="OIDC provider did not return an access token")
    verified = decode_access_token(str(access_token))
    return {
        "accessToken": access_token,
        "tokenType": data.get("token_type", "Bearer"),
        "expiresIn": data.get("expires_in"),
        "user": user_payload(verified),
    }


@router.get("/me")
def current_identity(auth: AuthContext = Depends(require_authenticated)) -> dict[str, Any]:
    return {"user": user_payload(auth)}


@router.post("/logout")
def logout(_: Request, auth: AuthContext = Depends(require_authenticated)) -> dict[str, Any]:
    return {"ok": True, "subject": auth.subject}

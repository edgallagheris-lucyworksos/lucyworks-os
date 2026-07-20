from __future__ import annotations

import json
import os
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

import jwt
from fastapi import HTTPException, Request
from jwt import PyJWKClient
from starlette.datastructures import Headers
from starlette.responses import JSONResponse

ALLOWED_ROLES = {
    "admin",
    "clinician",
    "clinical_director",
    "governance_lead",
    "hospital_director",
    "nurse",
    "ops_manager",
    "senior_clinician",
    "supervisor",
}
SENIOR_ROLES = {
    "clinical_director",
    "governance_lead",
    "hospital_director",
    "ops_manager",
    "senior_clinician",
    "supervisor",
}
CLINICAL_ROLES = {
    "clinician",
    "clinical_director",
    "nurse",
    "senior_clinician",
    "supervisor",
}
ALL_AUTHENTICATED_ROLES = ALLOWED_ROLES
PUBLIC_PATHS = {
    "/",
    "/api/health",
    "/api/auth/config",
    "/api/auth/dev-login",
    "/api/auth/oidc/exchange",
    "/docs",
    "/docs/oauth2-redirect",
    "/openapi.json",
    "/redoc",
}
PUBLIC_PREFIXES = (
    "/docs",
    "/api/integrations/webhooks/",
)


@dataclass(frozen=True)
class AuthContext:
    subject: str = "anonymous"
    actor_id: str | None = None
    actor_name: str = "unverified caller"
    role: str = "anonymous"
    email: str | None = None
    issuer: str | None = None
    auth_source: str = "unverified"
    verified: bool = False
    expires_at: datetime | None = None
    claims: dict[str, Any] = field(default_factory=dict)


_ANONYMOUS = AuthContext()
current_auth_context: ContextVar[AuthContext] = ContextVar("lucyworks_auth_context", default=_ANONYMOUS)


def _setting(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def auth_mode() -> str:
    return _setting("AUTH_MODE", "local").lower()


def auth_enforcement() -> str:
    value = _setting("AUTH_ENFORCEMENT", "audit").lower()
    return value if value in {"off", "audit", "required"} else "audit"


def dev_login_enabled() -> bool:
    return _setting("AUTH_DEV_LOGIN_ENABLED", "false").lower() in {"1", "true", "yes", "on"}


def _role_map() -> dict[str, str]:
    raw = _setting("AUTH_ROLE_MAP", "")
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
        return {str(key): str(value) for key, value in parsed.items()}
    except (TypeError, ValueError):
        return {}


def _extract_role(claims: dict[str, Any]) -> str:
    claim_name = _setting("OIDC_ROLE_CLAIM", "role")
    candidate = claims.get(claim_name) or claims.get("role") or claims.get("roles")
    values = candidate if isinstance(candidate, list) else [candidate]
    mapping = _role_map()
    for value in values:
        if not value:
            continue
        role = mapping.get(str(value), str(value)).strip().lower()
        if role in ALLOWED_ROLES:
            return role
    raise HTTPException(status_code=403, detail="authenticated identity has no permitted LucyWorks role")


def _context_from_claims(claims: dict[str, Any], source: str) -> AuthContext:
    role = _extract_role(claims)
    subject = str(claims.get("sub") or "")
    if not subject:
        raise HTTPException(status_code=401, detail="token subject missing")
    expires_at = None
    if claims.get("exp"):
        expires_at = datetime.fromtimestamp(float(claims["exp"]), timezone.utc)
    return AuthContext(
        subject=subject,
        actor_id=str(claims.get("uid") or claims.get("user_id") or subject),
        actor_name=str(claims.get("name") or claims.get("preferred_username") or claims.get("email") or subject),
        role=role,
        email=str(claims.get("email")) if claims.get("email") else None,
        issuer=str(claims.get("iss")) if claims.get("iss") else None,
        auth_source=source,
        verified=True,
        expires_at=expires_at,
        claims=claims,
    )


def decode_access_token(token: str) -> AuthContext:
    mode = auth_mode()
    audience = _setting("AUTH_AUDIENCE", "lucyworks-api")
    issuer = _setting("AUTH_ISSUER", "lucyworks-local")
    leeway = int(_setting("AUTH_CLOCK_SKEW_SECONDS", "30") or "30")

    try:
        if mode == "oidc":
            jwks_url = _setting("OIDC_JWKS_URL")
            oidc_issuer = _setting("OIDC_ISSUER") or issuer
            if not jwks_url or not oidc_issuer or not audience:
                raise HTTPException(status_code=503, detail="OIDC validation is not configured")
            signing_key = PyJWKClient(jwks_url).get_signing_key_from_jwt(token)
            algorithms = [item.strip() for item in _setting("OIDC_ALGORITHMS", "RS256").split(",") if item.strip()]
            claims = jwt.decode(
                token,
                signing_key.key,
                algorithms=algorithms,
                audience=audience,
                issuer=oidc_issuer,
                leeway=leeway,
                options={"require": ["exp", "iat", "sub", "iss"]},
            )
            return _context_from_claims(claims, "oidc_verified")

        secret = _setting("AUTH_JWT_SECRET")
        if not secret:
            raise HTTPException(status_code=503, detail="local token validation secret is not configured")
        claims = jwt.decode(
            token,
            secret,
            algorithms=["HS256"],
            audience=audience,
            issuer=issuer,
            leeway=leeway,
            options={"require": ["exp", "iat", "sub", "iss", "aud"]},
        )
        return _context_from_claims(claims, "local_signed_token")
    except HTTPException:
        raise
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(status_code=401, detail="access token expired") from exc
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status_code=401, detail="access token invalid") from exc


def issue_local_token(*, user_id: int | str, name: str, role: str, email: str | None) -> tuple[str, int]:
    if role not in ALLOWED_ROLES:
        raise HTTPException(status_code=403, detail="user role is not permitted")
    secret = _setting("AUTH_JWT_SECRET")
    if not secret:
        raise HTTPException(status_code=503, detail="AUTH_JWT_SECRET must be configured")
    now = datetime.now(timezone.utc)
    lifetime_minutes = int(_setting("AUTH_TOKEN_MINUTES", "60") or "60")
    expires = now + timedelta(minutes=max(5, lifetime_minutes))
    claims = {
        "sub": f"local-user:{user_id}",
        "uid": str(user_id),
        "name": name,
        "email": email,
        "role": role,
        "iss": _setting("AUTH_ISSUER", "lucyworks-local"),
        "aud": _setting("AUTH_AUDIENCE", "lucyworks-api"),
        "iat": int(now.timestamp()),
        "nbf": int(now.timestamp()),
        "exp": int(expires.timestamp()),
    }
    return jwt.encode(claims, secret, algorithm="HS256"), int((expires - now).total_seconds())


def get_current_auth_context() -> AuthContext:
    return current_auth_context.get()


def require_authenticated(request: Request) -> AuthContext:
    auth = getattr(request.state, "auth", _ANONYMOUS)
    if not auth.verified:
        raise HTTPException(status_code=401, detail="verified identity required")
    return auth


def require_roles(*roles: str) -> Callable[[Request], AuthContext]:
    allowed = set(roles)

    def dependency(request: Request) -> AuthContext:
        auth = require_authenticated(request)
        if auth.role not in allowed:
            raise HTTPException(status_code=403, detail=f"role {auth.role} is not permitted for this action")
        return auth

    return dependency


def required_roles_for(method: str, path: str) -> set[str] | None:
    method = method.upper()
    write = method in {"POST", "PUT", "PATCH", "DELETE"}

    if path.startswith("/api/evidence/approvals"):
        return SENIOR_ROLES if write else ALL_AUTHENTICATED_ROLES
    if path.startswith("/api/control-plane/ai-models") and write:
        return SENIOR_ROLES
    if path.startswith("/api/control-plane/controls") and write:
        return SENIOR_ROLES
    if path.startswith("/api/control-plane/critical-results") and write:
        return CLINICAL_ROLES | SENIOR_ROLES
    if path.startswith("/api/control-plane/services") and write:
        return SENIOR_ROLES
    if path.startswith("/api/control-plane"):
        return ALL_AUTHENTICATED_ROLES
    if path.startswith("/api/integrations/connections") and write:
        return SENIOR_ROLES
    if path.startswith("/api/integrations"):
        return ALL_AUTHENTICATED_ROLES
    if path.startswith("/api/evidence"):
        return ALL_AUTHENTICATED_ROLES
    if path.startswith("/api/patient-care") and write:
        return ALL_AUTHENTICATED_ROLES
    return None


class VerifiedIdentityMiddleware:
    """Validate bearer identity before protected API routes execute.

    AUTH_ENFORCEMENT=required protects every API route except the explicit
    public set. In audit mode, legacy routes remain reachable, while the
    evidence/control-plane/patient-care write surfaces are still protected.
    Integration webhooks are exempt from bearer authentication only because
    they perform their own timestamped HMAC verification.
    """

    def __init__(self, app: Any):
        self.app = app

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = str(scope.get("path") or "")
        method = str(scope.get("method") or "GET").upper()
        if path in PUBLIC_PATHS or any(path.startswith(prefix) for prefix in PUBLIC_PREFIXES):
            token = current_auth_context.set(_ANONYMOUS)
            try:
                scope.setdefault("state", {})["auth"] = _ANONYMOUS
                await self.app(scope, receive, send)
            finally:
                current_auth_context.reset(token)
            return

        headers = Headers(scope=scope)
        authorization = headers.get("authorization", "")
        auth = _ANONYMOUS
        auth_error: HTTPException | None = None
        if authorization.lower().startswith("bearer "):
            try:
                auth = decode_access_token(authorization.split(" ", 1)[1].strip())
            except HTTPException as exc:
                auth_error = exc

        required_roles = required_roles_for(method, path)
        must_authenticate = required_roles is not None or (auth_enforcement() == "required" and path.startswith("/api/"))
        if must_authenticate and (auth_error or not auth.verified):
            error = auth_error or HTTPException(status_code=401, detail="verified bearer token required")
            response = JSONResponse({"detail": error.detail}, status_code=error.status_code)
            await response(scope, receive, send)
            return
        if required_roles and auth.role not in required_roles:
            response = JSONResponse({"detail": f"role {auth.role} is not permitted for this action"}, status_code=403)
            await response(scope, receive, send)
            return

        scope.setdefault("state", {})["auth"] = auth
        token = current_auth_context.set(auth)
        try:
            await self.app(scope, receive, send)
        finally:
            current_auth_context.reset(token)

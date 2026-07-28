from __future__ import annotations

import json
from typing import Any

from app.auth import AuthContext


_NAME_FIELDS = {
    "actor",
    "actor_name",
    "actorName",
    "createdBy",
    "updatedBy",
    "recordedBy",
    "reviewedBy",
    "decidedBy",
    "acknowledgedBy",
    "requestedBy",
    "fromActor",
}
_ROLE_FIELDS = {
    "actor_role",
    "actorRole",
    "createdByRole",
    "updatedByRole",
    "recordedByRole",
    "reviewedByRole",
    "decidedByRole",
    "acknowledgedByRole",
    "fromRole",
}
_SUBJECT_FIELDS = {
    "actor_id",
    "actorId",
    "actorSubject",
    "createdBySubject",
    "updatedBySubject",
    "recordedBySubject",
    "reviewedBySubject",
    "decidedBySubject",
    "acknowledgedBySubject",
    "fromSubject",
}
_AUTH_FIELDS = {"actorAuthSource", "actor_auth_source", "authSource", "auth_source"}


def _rewrite(value: Any, auth: AuthContext, changed: list[str], path: str = "") -> Any:
    if isinstance(value, list):
        return [_rewrite(item, auth, changed, f"{path}[{index}]") for index, item in enumerate(value)]
    if not isinstance(value, dict):
        return value

    result: dict[str, Any] = {}
    for key, item in value.items():
        field_path = f"{path}.{key}" if path else key
        if key in _NAME_FIELDS:
            if item != auth.actor_name:
                changed.append(field_path)
            result[key] = auth.actor_name
        elif key in _ROLE_FIELDS:
            if item != auth.role:
                changed.append(field_path)
            result[key] = auth.role
        elif key in _SUBJECT_FIELDS:
            subject = auth.actor_id or auth.subject
            if item != subject:
                changed.append(field_path)
            result[key] = subject
        elif key in _AUTH_FIELDS:
            if item != auth.auth_source:
                changed.append(field_path)
            result[key] = auth.auth_source
        else:
            result[key] = _rewrite(item, auth, changed, field_path)
    return result


class VerifiedActorAttributionMiddlewareV25:
    """Replace caller-declared actor metadata with the verified request identity.

    Legacy request contracts are retained for compatibility, but identity evidence can no
    longer be selected by a browser payload. Target-person fields such as ``toActor``,
    ``responsibleActor`` and ``clientAuthorisedBy`` are deliberately not changed.
    """

    def __init__(self, app: Any):
        self.app = app

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        method = str(scope.get("method") or "GET").upper()
        path = str(scope.get("path") or "")
        state = scope.setdefault("state", {})
        auth = state.get("auth")
        headers = list(scope.get("headers") or [])
        content_type = next((value.decode("latin-1") for key, value in headers if key.lower() == b"content-type"), "")

        if (
            method not in {"POST", "PUT", "PATCH", "DELETE"}
            or not path.startswith("/api/")
            or "application/json" not in content_type.lower()
            or not isinstance(auth, AuthContext)
            or not auth.verified
        ):
            await self.app(scope, receive, send)
            return

        chunks: list[bytes] = []
        more_body = True
        while more_body:
            message = await receive()
            if message.get("type") != "http.request":
                await self.app(scope, receive, send)
                return
            chunks.append(message.get("body", b""))
            more_body = bool(message.get("more_body", False))

        original = b"".join(chunks)
        changed: list[str] = []
        rewritten = original
        if original:
            try:
                payload = json.loads(original.decode("utf-8"))
                payload = _rewrite(payload, auth, changed)
                rewritten = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
            except (UnicodeDecodeError, json.JSONDecodeError, TypeError):
                rewritten = original

        state["verified_actor_attribution_v25"] = {
            "rewrittenFields": changed,
            "actorSubject": auth.subject,
            "actorRole": auth.role,
            "authSource": auth.auth_source,
        }
        filtered_headers = [(key, value) for key, value in headers if key.lower() != b"content-length"]
        filtered_headers.append((b"content-length", str(len(rewritten)).encode("ascii")))
        scope["headers"] = filtered_headers

        delivered = False

        async def replay_receive() -> dict[str, Any]:
            nonlocal delivered
            if delivered:
                return {"type": "http.request", "body": b"", "more_body": False}
            delivered = True
            return {"type": "http.request", "body": rewritten, "more_body": False}

        await self.app(scope, replay_receive, send)

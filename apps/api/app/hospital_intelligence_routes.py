from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth import AuthContext, require_roles

router = APIRouter(prefix="/api/hospital-intelligence", tags=["hospital-intelligence-v5"])

READ_ROLES = (
    "admin",
    "clinician",
    "clinical_director",
    "governance_lead",
    "hospital_director",
    "nurse",
    "ops_manager",
    "pca",
    "radiographer",
    "senior_clinician",
    "supervisor",
)


def _catalogue_path() -> Path:
    return Path(__file__).resolve().parents[3] / "config" / "hospital-intelligence" / "referral-hospital-public-catalogue.v1.json"


@lru_cache(maxsize=1)
def _load_catalogue() -> dict[str, Any]:
    path = _catalogue_path()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RuntimeError(f"hospital intelligence catalogue is missing: {path}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"hospital intelligence catalogue is invalid JSON: {exc}") from exc

    required = {"catalogueVersion", "researchedAt", "sources", "hospitals", "roleTemplates", "departmentTemplates", "workflowPatterns"}
    missing = required - set(payload)
    if missing:
        raise RuntimeError(f"hospital intelligence catalogue is missing keys: {sorted(missing)}")
    return payload


def _contains(value: Any, needle: str) -> bool:
    return needle.casefold() in json.dumps(value, ensure_ascii=False).casefold()


@router.get("/summary")
def get_summary(
    _: AuthContext = Depends(require_roles(*READ_ROLES)),
) -> dict[str, Any]:
    payload = _load_catalogue()
    return {
        "catalogueVersion": payload["catalogueVersion"],
        "researchedAt": payload["researchedAt"],
        "hospitalCount": len(payload["hospitals"]),
        "roleCount": len(payload["roleTemplates"]),
        "departmentCount": len(payload["departmentTemplates"]),
        "workflowCount": len(payload["workflowPatterns"]),
        "sourceCount": len(payload["sources"]),
        "governance": payload["governance"],
    }


@router.get("/catalogue")
def get_catalogue(
    hospital: str | None = Query(default=None, description="Filter to a hospitalRef"),
    role_family: str | None = Query(default=None, alias="roleFamily"),
    department: str | None = Query(default=None),
    q: str | None = Query(default=None, min_length=2, max_length=100),
    _: AuthContext = Depends(require_roles(*READ_ROLES)),
) -> dict[str, Any]:
    payload = _load_catalogue()
    hospitals = payload["hospitals"]
    roles = payload["roleTemplates"]
    departments = payload["departmentTemplates"]
    workflows = payload["workflowPatterns"]
    sources = payload["sources"]

    if hospital:
        hospitals = [item for item in hospitals if item.get("hospitalRef") == hospital]
        if not hospitals:
            raise HTTPException(status_code=404, detail="hospital benchmark not found")
        source_refs = {ref for item in hospitals for ref in item.get("sourceRefs", [])}
        sources = [item for item in sources if item.get("sourceRef") in source_refs]
        roles = [item for item in roles if source_refs.intersection(item.get("sourceRefs", []))]
        departments = [item for item in departments if source_refs.intersection(item.get("sourceRefs", []))]
        workflows = [item for item in workflows if source_refs.intersection(item.get("sourceRefs", []))]

    if role_family:
        roles = [item for item in roles if item.get("family") == role_family]

    if department:
        departments = [item for item in departments if item.get("departmentRef") == department or department.casefold() in item.get("name", "").casefold()]

    if q:
        hospitals = [item for item in hospitals if _contains(item, q)]
        roles = [item for item in roles if _contains(item, q)]
        departments = [item for item in departments if _contains(item, q)]
        workflows = [item for item in workflows if _contains(item, q)]
        matched_source_refs = {
            ref
            for collection in (hospitals, roles, departments, workflows)
            for item in collection
            for ref in item.get("sourceRefs", [])
        }
        sources = [item for item in sources if item.get("sourceRef") in matched_source_refs or _contains(item, q)]

    return {
        "catalogueVersion": payload["catalogueVersion"],
        "researchedAt": payload["researchedAt"],
        "scope": payload["scope"],
        "governance": payload["governance"],
        "hospitals": hospitals,
        "roleTemplates": roles,
        "departmentTemplates": departments,
        "workflowPatterns": workflows,
        "sources": sources,
        "counts": {
            "hospitals": len(hospitals),
            "roles": len(roles),
            "departments": len(departments),
            "workflows": len(workflows),
            "sources": len(sources),
        },
    }

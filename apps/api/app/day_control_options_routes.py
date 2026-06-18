from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/api/day-control", tags=["day-control"])

STAFF_OPTIONS = [
    {"id": 101, "name": "Reception 1", "role": "reception", "area": "front_door"},
    {"id": 102, "name": "Reception 2", "role": "reception", "area": "front_door"},
    {"id": 201, "name": "Insurance Admin", "role": "insurance/admin", "area": "admin"},
    {"id": 301, "name": "Imaging Lead", "role": "imaging lead", "area": "imaging"},
    {"id": 302, "name": "Clinical Lead", "role": "clinical lead", "area": "clinical"},
    {"id": 401, "name": "Surgical Lead", "role": "surgical lead", "area": "theatre"},
    {"id": 402, "name": "Anaesthesia", "role": "anaesthesia", "area": "theatre"},
    {"id": 501, "name": "Nurse 1", "role": "nurse", "area": "ward"},
    {"id": 502, "name": "Nurse 2", "role": "nurse", "area": "ward"},
    {"id": 601, "name": "PCA 1", "role": "PCA", "area": "support"},
    {"id": 701, "name": "Client Contact", "role": "client contact", "area": "client"},
    {"id": 801, "name": "Ops Manager", "role": "ops manager", "area": "ops"},
]

RESOURCE_OPTIONS = [
    {"id": "reception", "name": "Reception", "type": "front_door"},
    {"id": "admin-queue", "name": "Admin queue", "type": "admin"},
    {"id": "consult-room", "name": "Consult room", "type": "consult"},
    {"id": "mri", "name": "MRI", "type": "imaging"},
    {"id": "ct", "name": "CT", "type": "imaging"},
    {"id": "theatre-1", "name": "Theatre 1", "type": "theatre"},
    {"id": "theatre-2", "name": "Theatre 2", "type": "theatre"},
    {"id": "recovery", "name": "Recovery", "type": "care"},
    {"id": "ward", "name": "Ward", "type": "care"},
    {"id": "client-contact", "name": "Client contact", "type": "communication"},
    {"id": "whole-hospital", "name": "Whole hospital", "type": "ops"},
]


@router.get("/staff-options")
def staff_options() -> dict[str, list[dict[str, object]]]:
    return {"staff": STAFF_OPTIONS}


@router.get("/resource-options")
def resource_options() -> dict[str, list[dict[str, object]]]:
    return {"resources": RESOURCE_OPTIONS}

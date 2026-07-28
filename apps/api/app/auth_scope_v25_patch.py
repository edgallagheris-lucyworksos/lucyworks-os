from __future__ import annotations

from app import auth as auth_module

_ORIGINAL_REQUIRED_ROLES_FOR = auth_module.required_roles_for
_HR_ROLES = {
    "admin",
    "clinical_director",
    "governance_lead",
    "hospital_director",
    "ops_manager",
    "supervisor",
}
_PATIENT_CARE_WRITE_ROLES = {
    "clinician",
    "clinical_director",
    "hospital_director",
    "nurse",
    "ops_manager",
    "senior_clinician",
    "supervisor",
}


def required_roles_for_v25(method: str, path: str) -> set[str] | None:
    method = method.upper()
    write = method in {"POST", "PUT", "PATCH", "DELETE"}
    if path.startswith("/api/v25/safety"):
        return auth_module.ALL_AUTHENTICATED_ROLES
    if path.startswith("/api/hr"):
        # The legacy HR surface contains organisation-wide absence, overtime and welfare data.
        # Employee self-service must use a future subject-bound route rather than selecting a staff id.
        return _HR_ROLES
    if path.startswith("/api/patient-care") and write:
        return _PATIENT_CARE_WRITE_ROLES
    return _ORIGINAL_REQUIRED_ROLES_FOR(method, path)


auth_module.required_roles_for = required_roles_for_v25

CANONICAL_ROLES = {
    "vet": ["full_access", "assign_case", "diagnose", "prescribe"],
    "nurse": ["limited_access", "administer_treatment", "log_notes"],
    "admin": ["billing", "client_comms"],
    "rota_coordinator": ["edit_rota", "reassign_cases"],
}


def permissions_for_role(role: str) -> list[str]:
    return CANONICAL_ROLES.get((role or "").lower(), [])


def role_can(role: str, permission: str) -> bool:
    return permission in permissions_for_role(role)

"""Extend authenticated hospital roles without widening clinical authority.

These roles can authenticate and receive explicitly approved site membership, but they
are not added to CLINICAL_ROLES or PRESCRIBER_ROLES. Existing route-level permissions
therefore remain the authority boundary.
"""
from app import auth

NON_CLINICAL_HOSPITAL_ROLES = {
    "reception",
    "referral_coordinator",
    "insurance",
    "pharmacy",
    "laboratory",
    "imaging",
    "ward_assistant",
    "facilities",
    "hr",
    "finance",
    "viewer",
}

auth.ALLOWED_ROLES.update(NON_CLINICAL_HOSPITAL_ROLES)
# ALL_AUTHENTICATED_ROLES is the same mutable set in current builds, but update it
# explicitly to retain the contract if that implementation changes.
auth.ALL_AUTHENTICATED_ROLES.update(NON_CLINICAL_HOSPITAL_ROLES)

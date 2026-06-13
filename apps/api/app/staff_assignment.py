ROLE_TO_STAFF_ROLES: dict[str, set[str]] = {
    "clinical_director_or_ops_manager": {"clinical_director", "ops_manager", "hospital_manager", "manager"},
    "owning_service_or_shift_lead": {"service_head", "consultant_specialist", "clinician", "senior_clinician", "nurse_lead"},
    "current_owner": {"clinician", "nurse", "admin", "ops_manager"},
    "receiving_role": {"nurse", "pca", "clinician", "admin", "support_services_lead"},
    "ops_manager": {"ops_manager", "hospital_manager", "manager"},
    "clinical_owner_or_senior": {"clinical_director", "service_head", "consultant_specialist", "senior_clinician", "clinician"},
    "admin_or_service_clinician": {"admin", "client_care", "referral_admin", "clinician", "service_clinician"},
    "insurance_admin": {"insurance_admin", "admin", "client_care"},
    "pharmacy_owner": {"pharmacy_owner", "nurse", "medical_nurse_lead"},
    "ward_or_icu_lead": {"medical_nurse_lead", "icu_nurse", "ward_nurse", "nurse_lead", "nurse"},
    "imaging_lead": {"imaging_lead", "radiologist", "radiographer", "imaging_nurse", "consultant_specialist"},
    "theatre_lead": {"theatre_nurse_lead", "theatre_lead", "theatre_nurse", "theatre_technician", "anaesthesia_nurse", "nurse"},
    "facilities_manager": {"facilities_manager", "ops_manager", "hospital_manager"},
}

QUEUE_TO_STAFF_ROLES: dict[str, set[str]] = {
    "escalation_queue": {"clinical_director", "ops_manager", "hospital_manager", "manager"},
    "role_queue": {"service_head", "consultant_specialist", "clinician", "nurse", "admin"},
    "handover_queue": {"nurse", "pca", "clinician", "admin"},
    "capacity_hold_queue": {"ops_manager", "hospital_manager", "facilities_manager"},
    "review_queue": {"clinical_director", "service_head", "consultant_specialist", "clinician"},
    "owner_comms_queue": {"admin", "client_care", "referral_admin", "clinician"},
    "insurance_queue": {"insurance_admin", "admin", "client_care"},
    "pharmacy_queue": {"pharmacy_owner", "nurse", "medical_nurse_lead"},
    "bed_capacity_queue": {"medical_nurse_lead", "icu_nurse", "ward_nurse", "nurse"},
    "imaging_queue": {"imaging_lead", "radiologist", "radiographer", "imaging_nurse"},
    "theatre_queue": {"theatre_nurse_lead", "theatre_lead", "theatre_nurse", "theatre_technician", "anaesthesia_nurse"},
}


def acceptable_staff_roles(role: str, queue: str | None = None) -> set[str]:
    roles = set()
    roles.update(ROLE_TO_STAFF_ROLES.get(role, {role}))
    if queue:
        roles.update(QUEUE_TO_STAFF_ROLES.get(queue, {queue}))
    return roles

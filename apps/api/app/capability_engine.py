from app.operating_catalogue import HOSPITAL_OPERATING_CATALOGUE


def find_procedure_template(procedure_name: str | None):
    if not procedure_name:
        return None
    for template in HOSPITAL_OPERATING_CATALOGUE.get("procedure_templates", []):
        if template.get("name", "").lower() == procedure_name.lower():
            return template
    return None


def find_department(name_or_short: str | None):
    if not name_or_short:
        return None
    for department in HOSPITAL_OPERATING_CATALOGUE.get("departments", []):
        if department.get("name") == name_or_short or department.get("short_name") == name_or_short:
            return department
    return None


def find_catalogue_row(collection: str, key: str, value: str | None):
    if not value:
        return None
    for row in HOSPITAL_OPERATING_CATALOGUE.get(collection, []):
        if row.get(key) == value:
            return row
    return None


def procedure_capability_profile(procedure_name: str):
    template = find_procedure_template(procedure_name)
    if not template:
        return None

    department = find_department(template.get("department"))
    family = find_catalogue_row("procedure_families", "family", template.get("family"))
    anaesthesia = find_catalogue_row("anaesthesia_levels", "level", template.get("anaesthesia_level"))
    recovery = find_catalogue_row("recovery_standards", "class", template.get("recovery_class"))
    cleaning = find_catalogue_row("cleaning_turnover_standards", "area", template.get("cleaning_standard"))

    required_roles = []
    if department:
        required_roles.extend(department.get("roles", []))
    required_roles.extend([
        anaesthesia.get("required_owner") if anaesthesia else None,
        recovery.get("owner_role") if recovery else None,
    ])
    required_roles = [role for role in dict.fromkeys([r for r in required_roles if r])]

    room_options = department.get("rooms", []) if department else []
    readiness_gates = []
    for source in [family, anaesthesia]:
        if source:
            readiness_gates.extend(source.get("required_gates", []) or source.get("readiness_gates", []))
    if recovery:
        readiness_gates.extend(recovery.get("minimum_checks", []))
    if cleaning:
        readiness_gates.extend(cleaning.get("checks", []))

    dependency_layers = []
    for layer in HOSPITAL_OPERATING_CATALOGUE.get("procedure_dependency_layers", []):
        name = layer.get("layer")
        include = False
        if name in {"case_identity", "clinical_owner", "consent_and_money", "room_and_flow", "staffing_and_skills", "audit"}:
            include = True
        if template.get("anaesthesia_level") != "none" and name == "anaesthesia_and_sedation":
            include = True
        if template.get("family") in {"Diagnostic imaging", "Medicine procedures", "Orthopaedics", "Neurology"} and name == "diagnostics_and_results":
            include = True
        if template.get("family") in {"Soft tissue surgery", "Orthopaedics", "Neurology", "Dental / oral"} and name in {"equipment_kit_and_implants", "pharmacy_and_meds", "stock_and_supplies", "recovery_and_care"}:
            include = True
        if template.get("recovery_class") in {"surgical", "critical"} and name == "recovery_and_care":
            include = True
        if template.get("cleaning_standard") == "isolation" and name == "infection_control":
            include = True
        if template.get("name") == "Discharge consultation" and name == "discharge":
            include = True
        if include:
            dependency_layers.append(layer)

    blockers_to_watch = []
    if department:
        blockers_to_watch.extend(department.get("common_blockers", []))
    blockers_to_watch.extend(template.get("risk", "").split("; ") if template.get("risk") else [])

    total_minutes = sum([
        template.get("prep_min", 0),
        template.get("anaesthesia_min", 0),
        template.get("procedure_min", 0),
        template.get("recovery_min", 0),
        template.get("cleaning_min", 0),
    ])

    return {
        "procedure": template,
        "department": department,
        "family": family,
        "anaesthesia": anaesthesia,
        "recovery": recovery,
        "cleaning": cleaning,
        "room_options": room_options,
        "required_roles": required_roles,
        "readiness_gates": list(dict.fromkeys(readiness_gates)),
        "dependency_layers": dependency_layers,
        "blockers_to_watch": list(dict.fromkeys([b for b in blockers_to_watch if b])),
        "total_minutes": total_minutes,
        "schedule_chain": [
            {"block_type": "prep", "minutes": template.get("prep_min", 0), "owner_role": "nurse"},
            {"block_type": "anaesthesia", "minutes": template.get("anaesthesia_min", 0), "owner_role": "anaesthetist"},
            {"block_type": "procedure", "minutes": template.get("procedure_min", 0), "owner_role": "clinician"},
            {"block_type": "recovery", "minutes": template.get("recovery_min", 0), "owner_role": "nurse"},
            {"block_type": "cleaning", "minutes": template.get("cleaning_min", 0), "owner_role": "nurse"},
        ],
    }


def all_capability_profiles():
    return [procedure_capability_profile(template["name"]) for template in HOSPITAL_OPERATING_CATALOGUE.get("procedure_templates", [])]

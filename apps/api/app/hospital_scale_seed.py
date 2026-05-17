from datetime import datetime, timedelta, timezone

from sqlmodel import Session, select

from app.inpatient_models import (
    FinancialConsentStatus,
    InpatientStay,
    MedicationDue,
    NightHandover,
    ObservationTask,
    OvernightEvent,
)
from app.models import (
    AuditEvent,
    CaseProcedure,
    Episode,
    HospitalSection,
    Patient,
    ProcedureType,
    Room,
    RoomState,
    ScheduleBlock,
    Shift,
    StaffMember,
    StockItem,
    User,
    WorkItem,
)
from app.operating_catalogue import HOSPITAL_OPERATING_CATALOGUE


SECTION_ROWS = [
    ("ECC", "emergency"),
    ("Resus", "emergency"),
    ("Prep", "procedures"),
    ("Anaesthesia", "procedures"),
    ("Diagnostics", "diagnostics"),
    ("Insurance", "admin_finance"),
    ("Owner Comms", "front_of_house"),
    ("Stock", "support"),
    ("Sterile Services", "support"),
]

ROOM_ROWS = [
    ("ECC", "Emergency Intake", "ecc"),
    ("Resus", "Resus Bay", "resus"),
    ("Triage", "Triage Bay 2", "triage"),
    ("Prep", "Prep Bay 1", "prep"),
    ("Prep", "Prep Bay 2", "prep"),
    ("Prep", "Prep Bay 3", "prep"),
    ("Prep", "Prep Bay 4", "prep"),
    ("Anaesthesia", "Anaesthesia Induction 1", "anaesthesia"),
    ("Anaesthesia", "Anaesthesia Induction 2", "anaesthesia"),
    *[("Theatres", f"Theatre {i}", "theatre") for i in range(3, 12)],
    ("Recovery", "Recovery Bay 1", "recovery"),
    ("Recovery", "Recovery Bay 2", "recovery"),
    ("Recovery", "Recovery Bay 3", "recovery"),
    ("Recovery", "Recovery Bay 4", "recovery"),
    ("Recovery", "Recovery Bay 5", "recovery"),
    ("ICU", "ICU Bay 1", "icu"),
    ("ICU", "ICU Bay 2", "icu"),
    ("ICU", "ICU Bay 3", "icu"),
    ("ICU", "ICU Bay 4", "icu"),
    ("ICU", "Oxygen Kennel", "oxygen"),
    ("ICU", "Isolation ICU", "isolation"),
    ("Wards", "Dog Ward", "ward"),
    ("Wards", "Cat Ward", "ward"),
    ("Wards", "Surgical Ward", "ward"),
    ("Wards", "High Dependency Ward", "ward"),
    ("Wards", "Isolation Ward", "isolation"),
    ("Imaging", "MRI", "mri"),
    ("Imaging", "CT", "ct"),
    ("Imaging", "X-ray", "xray"),
    ("Imaging", "Ultrasound", "ultrasound"),
    ("Imaging", "Imaging Prep", "imaging_prep"),
    ("Imaging", "Imaging Recovery", "imaging_recovery"),
    ("Lab", "Sample Prep", "lab"),
    ("Lab", "Bloods Bench", "lab"),
    ("Lab", "External Lab Dispatch", "lab_dispatch"),
    ("Pharmacy", "Dispensary", "pharmacy"),
    ("Pharmacy", "Controlled Drug Cabinet", "controlled_drug"),
    ("Pharmacy", "Cold Chain Fridge", "cold_chain"),
    ("Stock", "Main Stock", "stock"),
    ("Stock", "Theatre Stock", "stock"),
    ("Stock", "Ward Stock", "stock"),
    ("Sterile Services", "Sterile Store", "sterile_store"),
    ("Discharge", "Discharge Consult Room", "discharge"),
    ("Owner Comms", "Owner Comms Desk", "owner_comms"),
    ("Insurance", "Insurance / Estimate Desk", "insurance"),
]

STAFF_ROWS = [
    ("Dr Harper Clinical Director", "clinical_director", "senior review, escalation, governance"),
    ("Maya Flow Coordinator", "ops_manager", "flow, scheduling, escalation"),
    ("Dr Ellis ECC", "ecc_clinician", "ECC, resus, triage, critical care"),
    ("Nurse Reed ECC", "ecc_nurse", "triage, resus, oxygen, emergency"),
    ("Nurse Cole ICU", "icu_nurse", "ICU, q30 obs, fluids, oxygen"),
    ("Nurse Bright ICU", "icu_nurse", "ICU, overnight, critical recovery"),
    ("Dr Stone Soft Tissue", "surgeon", "soft tissue, GDV, wound reconstruction"),
    ("Dr Moss Orthopaedics", "orthopaedic_surgeon", "TPLO, fracture, arthroscopy, implants"),
    ("Dr Lane Neurology", "neurologist", "MRI, spinal, seizure, neuro surgery"),
    ("Dr West Medicine", "medicine_specialist", "ultrasound, endoscopy, medicine diagnostics"),
    ("Dr Field Dental", "dental_vet", "dental, oral surgery, dental xray"),
    ("Dr Quinn Anaesthesia", "anaesthetist", "GA, high-risk GA, sedation"),
    ("Nurse Patel Anaesthesia", "anaesthesia_nurse", "induction, monitoring, recovery handoff"),
    ("Nurse Brown Theatre", "theatre_nurse", "theatre, prep, circulating"),
    ("Nurse Green Scrub", "scrub_nurse", "scrub, sterile field, implants"),
    ("Nurse White Recovery", "recovery_nurse", "recovery, pain score, discharge handoff"),
    ("Nurse Black Ward", "ward_nurse", "wards, meds, inpatient care"),
    ("Nurse Grey Ward", "ward_nurse", "night ward, obs, handover"),
    ("Rae Radiographer", "radiographer", "CT, MRI, X-ray"),
    ("Dr Vale Radiologist", "radiologist", "imaging review, reports"),
    ("Pip Pharmacy Lead", "pharmacy_lead", "controlled drugs, discharge meds, cascade"),
    ("Sam Stock Controller", "stock_controller", "orders, sterile stock, cold chain"),
    ("Ari Admin", "admin", "reception, owner comms, discharge"),
    ("Ivy Insurance Admin", "insurance_admin", "estimates, direct claims, pre-authorisation"),
]


def ensure_section(session: Session, name: str, section_type: str):
    row = session.exec(select(HospitalSection).where(HospitalSection.name == name)).first()
    if not row:
        session.add(HospitalSection(name=name, section_type=section_type))


def ensure_room(session: Session, section_name: str, name: str, room_type: str):
    row = session.exec(select(Room).where(Room.name == name)).first()
    if not row:
        session.add(Room(section_name=section_name, name=name, room_type=room_type))


def ensure_room_state(session: Session, room_name: str, room_type: str, department: str, state: str = "available", current_episode_ref: str | None = None, next_episode_ref: str | None = None, cleaning_due_minutes: int | None = None):
    row = session.exec(select(RoomState).where(RoomState.room_name == room_name)).first()
    if not row:
        session.add(RoomState(room_name=room_name, room_type=room_type, department=department, state=state, current_episode_ref=current_episode_ref, next_episode_ref=next_episode_ref, cleaning_due_minutes=cleaning_due_minutes))


def ensure_user(session: Session, name: str, role: str):
    email = f"{name.lower().replace(' ', '.').replace('/', '')}@lucyworks.local"
    row = session.exec(select(User).where(User.email == email)).first()
    if not row:
        row = User(name=name, role=role, email=email)
        session.add(row)
        session.commit()
        session.refresh(row)
    return row


def ensure_staff(session: Session, name: str, role: str, skills: str):
    row = session.exec(select(StaffMember).where(StaffMember.name == name)).first()
    if row:
        return row
    user = ensure_user(session, name, role)
    row = StaffMember(user_id=user.id, name=name, role=role, skills=skills)
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def ensure_patient_episode(session: Session, patient_name: str, species: str, owner_name: str, episode_ref: str, section: str, room: str, phase: str):
    patient = session.exec(select(Patient).where(Patient.patient_name == patient_name)).first()
    if not patient:
        patient = Patient(patient_name=patient_name, species=species, owner_name=owner_name, owner_phone="07000000000", weight_kg=20.0)
        session.add(patient)
        session.commit()
        session.refresh(patient)
    ep = session.exec(select(Episode).where(Episode.episode_ref == episode_ref)).first()
    if not ep:
        ep = Episode(episode_ref=episode_ref, patient_id=patient.id, current_section_name=section, current_room_name=room, current_phase=phase)
        session.add(ep)
        session.commit()
        session.refresh(ep)
    return ep


def seed_procedure_types(session: Session):
    existing = {p.name for p in session.exec(select(ProcedureType)).all()}
    for template in HOSPITAL_OPERATING_CATALOGUE.get("procedure_templates", []):
        if template["name"] in existing:
            continue
        session.add(ProcedureType(
            name=template["name"],
            department=template["department"],
            default_duration_min=template.get("procedure_min", 0),
            prep_min=template.get("prep_min", 0),
            anaesthesia_min=template.get("anaesthesia_min", 0),
            recovery_min=template.get("recovery_min", 0),
            cleaning_min=template.get("cleaning_min", 0),
            required_role="clinician",
            required_room_type="theatre" if template["department"] in {"Surgery", "Orthopaedics", "Neurology", "Dental"} else "imaging" if template["department"] in {"Imaging", "Medicine"} else "clinical",
        ))
    session.commit()


def schedule_chain(session: Session, ep: Episode, procedure_name: str, start: datetime, room_name: str, staff_id: int | None = None):
    pt = session.exec(select(ProcedureType).where(ProcedureType.name == procedure_name)).first()
    if not pt:
        return
    cp = CaseProcedure(episode_id=ep.id, procedure_type_id=pt.id, scheduled_start=start)
    session.add(cp)
    session.commit()
    session.refresh(cp)
    chain = [
        ("prep", pt.prep_min, "nurse", room_name.replace("Theatre", "Prep Bay") if "Theatre" in room_name else room_name),
        ("anaesthesia", pt.anaesthesia_min, "anaesthetist", room_name),
        ("procedure", pt.default_duration_min, pt.required_role, room_name),
        ("recovery", pt.recovery_min, "recovery_nurse", "Recovery Bay 1"),
        ("cleaning", pt.cleaning_min, "theatre_nurse", room_name),
    ]
    cur = start
    for block_type, minutes, owner_role, block_room in chain:
        if minutes <= 0:
            continue
        block = ScheduleBlock(
            episode_id=ep.id,
            case_procedure_id=cp.id,
            block_type=block_type,
            room_name=block_room,
            owner_role=owner_role,
            assigned_staff_member_id=staff_id,
            starts_at=cur,
            ends_at=cur + timedelta(minutes=minutes),
            status="planned",
        )
        session.add(block)
        cur = block.ends_at
    session.commit()


def seed_hospital_scale(session: Session) -> None:
    for name, section_type in SECTION_ROWS:
        ensure_section(session, name, section_type)
    session.commit()

    for section_name, name, room_type in ROOM_ROWS:
        ensure_room(session, section_name, name, room_type)
    session.commit()

    for section_name, name, room_type in ROOM_ROWS:
        ensure_room_state(session, name, room_type, section_name)
    session.commit()

    staff_by_name = {}
    for name, role, skills in STAFF_ROWS:
        staff_by_name[name] = ensure_staff(session, name, role, skills)

    now = datetime.now(timezone.utc).replace(hour=7, minute=0, second=0, microsecond=0)
    for staff in staff_by_name.values():
        has_shift = session.exec(select(Shift).where(Shift.staff_member_id == staff.id)).first()
        if not has_shift:
            shift_type = "night" if "Night" in staff.name or staff.role in {"icu_nurse", "ward_nurse", "ecc_nurse"} else "day"
            starts = now if shift_type == "day" else now.replace(hour=19)
            ends = now.replace(hour=19) if shift_type == "day" else now + timedelta(days=1)
            session.add(Shift(staff_member_id=staff.id, department="Hospital", starts_at=starts, ends_at=ends, shift_type=shift_type, status="active"))
    session.commit()

    seed_procedure_types(session)

    cases = [
        ("Atlas", "Dog", "Owner A", "EP-2001", "Theatres", "Theatre 3", "procedure", "TPLO", "Theatre 3", 8),
        ("Juno", "Dog", "Owner B", "EP-2002", "Theatres", "Theatre 4", "procedure", "Fracture repair", "Theatre 4", 8),
        ("Mabel", "Dog", "Owner C", "EP-2003", "Theatres", "Theatre 5", "procedure", "Foreign body surgery", "Theatre 5", 9),
        ("Scout", "Dog", "Owner D", "EP-2004", "Imaging", "MRI", "imaging", "MRI scan", "MRI", 10),
        ("Cleo", "Cat", "Owner E", "EP-2005", "Imaging", "CT", "imaging", "CT scan", "CT", 11),
        ("Nell", "Dog", "Owner F", "EP-2006", "ICU", "ICU Bay 1", "critical_care", "Initial ECC stabilisation", "Resus Bay", 7),
        ("Bert", "Dog", "Owner G", "EP-2007", "Wards", "Surgical Ward", "overnight", "Discharge consultation", "Discharge Consult Room", 12),
        ("Tilly", "Cat", "Owner H", "EP-2008", "Wards", "Cat Ward", "overnight", "Dental extraction block", "Theatre 6", 13),
    ]
    for patient_name, species, owner, ref, section, room, phase, proc, proc_room, hour in cases:
        ep = ensure_patient_episode(session, patient_name, species, owner, ref, section, room, phase)
        schedule_chain(session, ep, proc, now.replace(hour=hour), proc_room)

    inpatient_specs = [
        ("EP-2001", "Surgical Ward", "Kennel S1", "surgical", 120, "TPLO post-op overnight; pain scoring and morning ortho review."),
        ("EP-2002", "High Dependency Ward", "HD2", "high_dependency", 60, "Fracture repair overnight; neurovascular checks."),
        ("EP-2006", "ICU Bay 1", "ICU1", "critical", 30, "ECC stabilisation overnight; oxygen and perfusion checks."),
        ("EP-1051", "ICU Bay 2", "ICU2", "critical", 30, "Existing ICU patient carry-over from seed data."),
        ("EP-1042", "Dog Ward", "Kennel D4", "routine", 240, "Existing ward patient carry-over pending owner update."),
        ("EP-1053", "Cat Ward", "Kennel C2", "routine", 240, "Existing cat ward patient carry-over."),
    ]
    for ref, room, bed, acuity, freq, notes in inpatient_specs:
        ep = session.exec(select(Episode).where(Episode.episode_ref == ref)).first()
        if not ep:
            continue
        existing = session.exec(select(InpatientStay).where(InpatientStay.episode_id == ep.id)).first()
        if not existing:
            stay = InpatientStay(episode_id=ep.id, location_room=room, bed_label=bed, acuity=acuity, obs_frequency_minutes=freq, expected_discharge_at=now + timedelta(days=1, hours=3), notes=notes)
            session.add(stay)
            session.commit()
            session.refresh(stay)
            for offset, task_type in [(0, "evening obs"), (freq, "overnight obs"), (freq * 2, "pain score"), (freq * 3, "morning prep")]:
                session.add(ObservationTask(episode_id=ep.id, inpatient_stay_id=stay.id, task_type=task_type, detail=f"{task_type} for {ref} in {room}/{bed}", due_at=now.replace(hour=19) + timedelta(minutes=offset), frequency_minutes=freq, owner_role="icu_nurse" if acuity == "critical" else "ward_nurse", escalation_required=acuity in {"critical", "high_dependency"}))
            session.add(MedicationDue(episode_id=ep.id, inpatient_stay_id=stay.id, medication_name="Analgesia as charted", due_at=now.replace(hour=22), owner_role="nurse", controlled_or_legal_status="controlled" if acuity in {"critical", "surgical"} else "standard"))
            session.add(MedicationDue(episode_id=ep.id, inpatient_stay_id=stay.id, medication_name="Morning medication round", due_at=now + timedelta(days=1, hours=-1), owner_role="nurse"))
            session.add(NightHandover(episode_id=ep.id, inpatient_stay_id=stay.id, from_role="day_team", to_role="night_team", risk_level="red" if acuity == "critical" else "amber", summary=notes, meds_due_summary="Analgesia and morning meds due", obs_plan=f"Obs every {freq} minutes", morning_decision_required="Morning clinician review", owner_update_status="due", acknowledged=False))
            session.add(FinancialConsentStatus(episode_id=ep.id, consent_status="signed" if acuity != "critical" else "urgent_verbal", estimate_status="accepted" if acuity != "critical" else "needs_update", insurance_status="pre_authorisation_pending" if acuity in {"critical", "surgical"} else "unknown", payment_status="deposit_taken" if acuity != "critical" else "pending", direct_claim_status="pending", pre_authorisation_status="pending" if acuity in {"critical", "surgical"} else "not_applicable", owner_financial_constraint=acuity == "critical", pharmacy_blocked=acuity == "critical", discharge_blocked=True, material_decision_required=acuity in {"critical", "surgical"}, notes="Financial/insurance status linked to overnight and discharge/pharmacy flow."))
            if acuity == "critical":
                session.add(OvernightEvent(episode_id=ep.id, inpatient_stay_id=stay.id, event_type="respiratory_monitoring", severity="high", detail="Q30 checks required overnight; on-call clinician escalation if deterioration.", owner_role="icu_nurse"))
            session.add(WorkItem(title=f"Overnight inpatient plan: {ref}", input_type="overnight_care", source="inpatient", category="overnight", description=notes, urgency="red" if acuity == "critical" else "amber", owner_role="icu_nurse" if acuity == "critical" else "ward_nurse", section_name="ICU" if acuity == "critical" else "Wards", room_name=room, patient_location_label=bed, linked_episode_ref=ref, status="new"))
    session.commit()

    for room in ["MRI", "CT", "X-ray", "Ultrasound", "Theatre 3", "Theatre 4", "Theatre 5", "Theatre 6", "ICU Bay 1", "Surgical Ward", "High Dependency Ward", "Dog Ward", "Cat Ward", "Dispensary", "Insurance / Estimate Desk"]:
        state = session.exec(select(RoomState).where(RoomState.room_name == room)).first()
        if state:
            state.state = "occupied" if room in {"MRI", "CT", "Theatre 3", "Theatre 4", "Theatre 5", "ICU Bay 1", "Surgical Ward", "High Dependency Ward", "Dog Ward", "Cat Ward"} else "active"
            session.add(state)
    for item in [
        StockItem(name="TPLO plate set", category="implant", location="Theatre Stock", current_quantity=1, reorder_threshold=2, authorised_supplier="NVS", compliance_note="Implant availability affects orthopaedic theatre flow"),
        StockItem(name="Methadone", category="controlled_drug", location="Controlled Drug Cabinet", current_quantity=2, reorder_threshold=3, authorised_supplier="MWI", compliance_note="Controlled medicine audit required"),
        StockItem(name="IV catheter 22G", category="consumable", location="Ward Stock", current_quantity=4, reorder_threshold=10, authorised_supplier="Covetrus", compliance_note="Low stock blocks ward/theatre prep"),
    ]:
        exists = session.exec(select(StockItem).where(StockItem.name == item.name)).first()
        if not exists:
            session.add(item)
    session.commit()

    session.add(AuditEvent(actor_name="System", action="seeded", entity_type="hospital_scale", entity_id=0, summary="Hospital-scale rooms, staff, procedures, schedule blocks, overnight inpatient and finance/insurance state seeded."))
    session.commit()

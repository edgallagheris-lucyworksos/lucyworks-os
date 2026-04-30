from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.capability_engine import all_capability_profiles, procedure_capability_profile
from app.database import get_session
from app.models import AuditEvent, CaseProcedure, Episode, ProcedureType, ScheduleBlock
from app.operating_catalogue import HOSPITAL_OPERATING_CATALOGUE

router = APIRouter()


def log(session: Session, actor: str, action: str, entity: str, entity_id: int, summary: str):
    session.add(AuditEvent(actor_name=actor, action=action, entity_type=entity, entity_id=entity_id, summary=summary))
    session.commit()


def find_template(name: str):
    for template in HOSPITAL_OPERATING_CATALOGUE["procedure_templates"]:
        if template["name"].lower() == name.lower():
            return template
    return None


def find_by_key(collection: str, key: str, value: str):
    for row in HOSPITAL_OPERATING_CATALOGUE.get(collection, []):
        if row.get(key) == value:
            return row
    return None


@router.get("/api/operating-catalogue")
def operating_catalogue():
    return HOSPITAL_OPERATING_CATALOGUE


@router.get("/api/operating-catalogue/departments")
def operating_departments():
    return HOSPITAL_OPERATING_CATALOGUE["departments"]


@router.get("/api/operating-catalogue/procedures")
def operating_procedures():
    return HOSPITAL_OPERATING_CATALOGUE["procedure_templates"]


@router.get("/api/operating-catalogue/procedures/{procedure_name}")
def operating_procedure_detail(procedure_name: str):
    template = find_template(procedure_name)
    if not template:
        raise HTTPException(status_code=404, detail="Procedure template not found")
    return template


@router.get("/api/capability/procedures")
def capability_profiles():
    return all_capability_profiles()


@router.get("/api/capability/procedures/{procedure_name}")
def capability_profile(procedure_name: str):
    profile = procedure_capability_profile(procedure_name)
    if not profile:
        raise HTTPException(status_code=404, detail="Procedure capability profile not found")
    return profile


@router.get("/api/episode-operating-readiness/{episode_ref}")
def episode_operating_readiness(episode_ref: str, session: Session = Depends(get_session)):
    episode = session.exec(select(Episode).where(Episode.episode_ref == episode_ref)).first()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")
    case_procedures = session.exec(select(CaseProcedure).where(CaseProcedure.episode_id == episode.id)).all()
    procedure_rows = []
    missing_templates = []
    for case_procedure in case_procedures:
      proc_type = session.get(ProcedureType, case_procedure.procedure_type_id)
      if not proc_type:
          continue
      template = find_template(proc_type.name)
      capability = procedure_capability_profile(proc_type.name)
      if not template or not capability:
          missing_templates.append(proc_type.name)
          continue
      blocks = session.exec(select(ScheduleBlock).where(ScheduleBlock.case_procedure_id == case_procedure.id).order_by(ScheduleBlock.starts_at)).all()
      expected = [block["block_type"] for block in capability["schedule_chain"] if block["minutes"] > 0]
      actual = [b.block_type for b in blocks]
      missing_blocks = [name for name in expected if name not in actual]
      procedure_rows.append({
          "case_procedure_id": case_procedure.id,
          "procedure_name": proc_type.name,
          "template": template,
          "capability": capability,
          "family": capability.get("family"),
          "anaesthesia": capability.get("anaesthesia"),
          "recovery": capability.get("recovery"),
          "cleaning": capability.get("cleaning"),
          "expected_blocks": expected,
          "actual_blocks": actual,
          "missing_blocks": missing_blocks,
          "readiness_gates": capability.get("readiness_gates", []),
          "dependency_layers": capability.get("dependency_layers", []),
          "ready": len(missing_blocks) == 0,
      })
    blockers = []
    for row in procedure_rows:
        for missing in row["missing_blocks"]:
            blockers.append({"type": "missing_schedule_block", "procedure": row["procedure_name"], "detail": f"Missing {missing} block"})
    return {
        "episode_ref": episode_ref,
        "procedure_count": len(procedure_rows),
        "procedures": procedure_rows,
        "missing_templates": missing_templates,
        "operating_blockers": blockers,
        "ready": len(blockers) == 0 and len(missing_templates) == 0,
    }


@router.post("/api/operating-catalogue/schedule-from-template")
def schedule_from_template(payload: dict, session: Session = Depends(get_session)):
    episode_ref = payload.get("episode_ref")
    procedure_name = payload.get("procedure_name")
    room_name = payload.get("room_name") or "Unassigned"
    actor_name = payload.get("actor_name", "Operating Model")
    start_time_raw = payload.get("start_time")
    if not episode_ref or not procedure_name or not start_time_raw:
        raise HTTPException(status_code=400, detail="episode_ref, procedure_name and start_time are required")

    capability = procedure_capability_profile(procedure_name)
    if not capability:
        raise HTTPException(status_code=404, detail="Procedure capability profile not found")
    template = capability["procedure"]

    if room_name != "Unassigned" and capability["room_options"] and room_name not in capability["room_options"]:
        raise HTTPException(status_code=400, detail=f"Room '{room_name}' is not listed for {procedure_name}. Options: {capability['room_options']}")

    episode = session.exec(select(Episode).where(Episode.episode_ref == episode_ref)).first()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")

    start_time = datetime.fromisoformat(start_time_raw.replace("Z", "+00:00"))

    proc_type = session.exec(select(ProcedureType).where(ProcedureType.name == template["name"])).first()
    if not proc_type:
        proc_type = ProcedureType(
            name=template["name"],
            department=template["department"],
            default_duration_min=template["procedure_min"],
            prep_min=template["prep_min"],
            recovery_min=template["recovery_min"],
            cleaning_min=template["cleaning_min"],
            required_role="clinician",
            notes=template["risk"],
        )
        session.add(proc_type)
        session.commit()
        session.refresh(proc_type)

    case_procedure = CaseProcedure(episode_id=episode.id, procedure_type_id=proc_type.id, scheduled_start=start_time)
    session.add(case_procedure)
    session.commit()
    session.refresh(case_procedure)

    blocks = []
    current = start_time
    for chain_block in capability["schedule_chain"]:
        block_type = chain_block["block_type"]
        minutes = chain_block["minutes"]
        owner_role = chain_block["owner_role"]
        if minutes <= 0:
            continue
        block = ScheduleBlock(
            episode_id=episode.id,
            case_procedure_id=case_procedure.id,
            block_type=block_type,
            room_name=room_name,
            owner_role=owner_role,
            starts_at=current,
            ends_at=current + timedelta(minutes=minutes),
        )
        current = block.ends_at
        session.add(block)
        blocks.append(block)

    episode.current_phase = "scheduled"
    episode.current_room_name = room_name
    episode.current_section_name = template["department"]
    session.add(episode)
    session.commit()

    log(session, actor_name, "capability_schedule_generated", "case_procedure", case_procedure.id or 0, f"{episode_ref} scheduled from {template['name']} capability profile")
    return {
        "template": template,
        "capability": capability,
        "case_procedure": case_procedure,
        "blocks": blocks,
        "total_minutes": capability["total_minutes"],
    }


@router.get("/api/operating-catalogue/pharmacy-governance")
def operating_pharmacy_governance():
    return HOSPITAL_OPERATING_CATALOGUE["pharmacy_governance"]


@router.get("/api/operating-catalogue/compliance")
def operating_compliance():
    return {
        "legal_and_compliance_guardrails": HOSPITAL_OPERATING_CATALOGUE["legal_and_compliance_guardrails"],
        "operating_rules": HOSPITAL_OPERATING_CATALOGUE["operating_rules"],
    }

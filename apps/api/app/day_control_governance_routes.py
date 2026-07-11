from __future__ import annotations

from collections import defaultdict
from typing import Any

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app.database import get_session
from app.schedule_state_models import ScheduleStateBlock

router = APIRouter(prefix="/api/day-control", tags=["day-control-governance"])

PROCEDURE_TERMS = {"mri", "ct", "theatre", "surgery", "surgical", "anaesthesia", "anaesthetic", "procedure", "imaging"}
CONSENT_TERMS = {"consent", "owner consent"}
ESTIMATE_TERMS = {"estimate", "cost", "payment"}
INSURANCE_TERMS = {"insurance", "claim", "preauth", "pre-authorisation", "preauthorization"}
PHARMACY_TERMS = {"pharmacy", "medication", "meds", "drug", "contrast", "discharge meds", "analgesia", "anaesthetic induction"}
OWNER_UPDATE_TERMS = {"owner update", "client update", "contact owner", "owner call", "client contact"}
REFERRING_VET_TERMS = {"referring vet", "report", "referral report", "letter"}
DISCHARGE_TERMS = {"discharge", "home"}
DONE_TERMS = {"complete", "completed", "done", "sent", "recorded", "clear", "cleared", "ready", "authorised", "authorized", "approved", "updated"}
BAD_TERMS = {"missing", "pending", "query", "blocked", "not ready", "not sent", "required", "needed", "awaiting"}


def _text(row: ScheduleStateBlock) -> str:
    return f"{row.what} {row.who} {row.where} {row.how} {row.blocker} {row.next} {row.lane}".lower()


def _row(row: ScheduleStateBlock) -> dict[str, Any]:
    return {
        "id": row.id,
        "time": row.time,
        "lane": row.lane,
        "what": row.what,
        "who": row.who,
        "where": row.where,
        "status": row.status,
        "blocker": row.blocker,
        "next": row.next,
        "subject": row.subject,
        "episodeRef": row.episode_ref,
        "assignedRole": row.assigned_role,
        "assignedStaffId": row.assigned_staff_id,
        "assignedStaffName": row.assigned_staff_name,
        "resourceId": row.resource_id,
        "resourceName": row.resource_name,
    }


def _case_key(row: ScheduleStateBlock) -> str:
    return row.episode_ref or row.subject or row.id


def _contains(text: str, terms: set[str]) -> bool:
    return any(term in text for term in terms)


def _is_done(row: ScheduleStateBlock) -> bool:
    text = _text(row)
    if row.status == "green" and (not row.blocker or row.blocker == "none"):
        return True
    return _contains(text, DONE_TERMS) and not _contains(text, BAD_TERMS)


def _is_bad(row: ScheduleStateBlock) -> bool:
    text = _text(row)
    return row.status == "red" or (row.blocker and row.blocker != "none") or _contains(text, BAD_TERMS)


def _matching(rows: list[ScheduleStateBlock], terms: set[str]) -> list[ScheduleStateBlock]:
    return [row for row in rows if _contains(_text(row), terms)]


def _has_clear(rows: list[ScheduleStateBlock], terms: set[str]) -> bool:
    return any(_is_done(row) for row in _matching(rows, terms))


def _blocked_rows(rows: list[ScheduleStateBlock], terms: set[str]) -> list[ScheduleStateBlock]:
    return [row for row in _matching(rows, terms) if _is_bad(row)]


def _has_procedure(rows: list[ScheduleStateBlock]) -> bool:
    return any(_contains(_text(row), PROCEDURE_TERMS) for row in rows)


def _has_discharge(rows: list[ScheduleStateBlock]) -> bool:
    return any(_contains(_text(row), DISCHARGE_TERMS) for row in rows)


def _gate(gates: list[dict[str, Any]], case_id: str, severity: str, gate_type: str, title: str, detail: str, rows: list[ScheduleStateBlock]) -> None:
    gates.append({
        "type": gate_type,
        "severity": severity,
        "caseId": case_id,
        "title": title,
        "detail": detail,
        "blocks": [_row(row) for row in rows],
    })


@router.get("/governance-gates")
def list_governance_gates(session: Session = Depends(get_session)) -> dict[str, Any]:
    blocks = session.exec(select(ScheduleStateBlock).order_by(ScheduleStateBlock.time, ScheduleStateBlock.lane)).all()
    grouped: dict[str, list[ScheduleStateBlock]] = defaultdict(list)
    for block in blocks:
        grouped[_case_key(block)].append(block)

    gates: list[dict[str, Any]] = []

    for case_id, rows in grouped.items():
        if not _has_procedure(rows) and not _has_discharge(rows):
            continue

        procedure_rows = [row for row in rows if _contains(_text(row), PROCEDURE_TERMS)] or rows
        discharge_rows = [row for row in rows if _contains(_text(row), DISCHARGE_TERMS)] or rows

        consent_blockers = _blocked_rows(rows, CONSENT_TERMS)
        estimate_blockers = _blocked_rows(rows, ESTIMATE_TERMS)
        insurance_blockers = _blocked_rows(rows, INSURANCE_TERMS)
        pharmacy_blockers = _blocked_rows(rows, PHARMACY_TERMS)
        owner_update_blockers = _blocked_rows(rows, OWNER_UPDATE_TERMS)
        report_blockers = _blocked_rows(rows, REFERRING_VET_TERMS)

        if _has_procedure(rows) and not _has_clear(rows, CONSENT_TERMS):
            _gate(gates, case_id, "red", "consent_gate", "Procedure blocked: consent not clear", "No clear consent block is recorded for this referral pathway.", procedure_rows)
        if _has_procedure(rows) and not _has_clear(rows, ESTIMATE_TERMS):
            _gate(gates, case_id, "red", "estimate_gate", "Procedure blocked: estimate not clear", "No clear estimate/cost approval is recorded for this referral pathway.", procedure_rows)
        if insurance_blockers:
            _gate(gates, case_id, "amber", "insurance_gate", "Insurance/admin issue open", "Insurance, claim, estimate, or payment work still carries a blocker.", insurance_blockers)
        if _has_procedure(rows) and pharmacy_blockers:
            _gate(gates, case_id, "red", "pharmacy_gate", "Procedure blocked: pharmacy not ready", "Medication, contrast, anaesthesia or discharge medication task is not ready.", pharmacy_blockers)
        if _has_discharge(rows) and not _has_clear(rows, OWNER_UPDATE_TERMS):
            _gate(gates, case_id, "red", "owner_update_gate", "Discharge blocked: owner update missing", "No clear owner/client update is recorded before discharge.", discharge_rows)
        if _has_discharge(rows) and not _has_clear(rows, REFERRING_VET_TERMS):
            _gate(gates, case_id, "amber", "referring_vet_report_gate", "Case cannot close: referring-vet report missing", "No clear referring-vet report/letter sent state is recorded.", discharge_rows)
        if owner_update_blockers:
            _gate(gates, case_id, "amber", "owner_update_blocker", "Owner/client update still blocked", "Owner/client communication has an unresolved blocker.", owner_update_blockers)
        if report_blockers:
            _gate(gates, case_id, "amber", "referring_vet_report_blocker", "Referring-vet report still blocked", "Referral report/letter has an unresolved blocker.", report_blockers)

    severity_order = {"red": 0, "amber": 1, "green": 2}
    gates.sort(key=lambda item: (severity_order.get(str(item.get("severity")), 9), str(item.get("caseId")), str(item.get("type"))))
    return {"gates": gates, "count": len(gates)}

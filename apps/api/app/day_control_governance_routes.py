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
CLEAR_STATUSES = {"clear", "cleared", "approved", "authorised", "authorized", "complete", "completed", "done", "ready"}
OPEN_STATUSES = {"missing", "pending", "query", "blocked", "not_ready", "not ready", "required", "needed", "awaiting"}


def _normal(value: str | None) -> str:
    return (value or "").strip().lower().replace("-", "_")


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
        "consentStatus": row.consent_status,
        "estimateStatus": row.estimate_status,
        "insuranceStatus": row.insurance_status,
        "pharmacyReady": row.pharmacy_ready,
        "ownerUpdated": row.owner_updated,
        "referringVetReportSent": row.referring_vet_report_sent,
        "dischargeClear": row.discharge_clear,
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


def _explicit_status(rows: list[ScheduleStateBlock], attr: str) -> list[str]:
    return [_normal(getattr(row, attr)) for row in rows if getattr(row, attr) is not None]


def _explicit_bool(rows: list[ScheduleStateBlock], attr: str) -> list[bool]:
    return [bool(getattr(row, attr)) for row in rows if getattr(row, attr) is not None]


def _explicit_clear(rows: list[ScheduleStateBlock], attr: str) -> bool | None:
    values = _explicit_status(rows, attr)
    if not values:
        return None
    return any(value in CLEAR_STATUSES for value in values)


def _explicit_open(rows: list[ScheduleStateBlock], attr: str) -> bool | None:
    values = _explicit_status(rows, attr)
    if not values:
        return None
    return any(value in OPEN_STATUSES for value in values) or not any(value in CLEAR_STATUSES for value in values)


def _explicit_bool_clear(rows: list[ScheduleStateBlock], attr: str) -> bool | None:
    values = _explicit_bool(rows, attr)
    if not values:
        return None
    return any(values)


def _explicit_bool_open(rows: list[ScheduleStateBlock], attr: str) -> bool | None:
    values = _explicit_bool(rows, attr)
    if not values:
        return None
    return not any(values)


def _has_procedure(rows: list[ScheduleStateBlock]) -> bool:
    return any(_contains(_text(row), PROCEDURE_TERMS) for row in rows)


def _has_discharge(rows: list[ScheduleStateBlock]) -> bool:
    return any(_contains(_text(row), DISCHARGE_TERMS) or row.discharge_clear is not None for row in rows)


def _gate(gates: list[dict[str, Any]], case_id: str, severity: str, gate_type: str, title: str, detail: str, rows: list[ScheduleStateBlock], source: str = "explicit_state") -> None:
    gates.append({
        "type": gate_type,
        "severity": severity,
        "caseId": case_id,
        "title": title,
        "detail": detail,
        "source": source,
        "blocks": [_row(row) for row in rows],
    })


def _state_rows(rows: list[ScheduleStateBlock], attr: str) -> list[ScheduleStateBlock]:
    matching = [row for row in rows if getattr(row, attr) is not None]
    return matching or rows


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
        discharge_rows = [row for row in rows if _contains(_text(row), DISCHARGE_TERMS) or row.discharge_clear is not None] or rows

        consent_clear = _explicit_clear(rows, "consent_status")
        estimate_clear = _explicit_clear(rows, "estimate_status")
        insurance_open = _explicit_open(rows, "insurance_status")
        pharmacy_open = _explicit_bool_open(rows, "pharmacy_ready")
        owner_updated = _explicit_bool_clear(rows, "owner_updated")
        report_sent = _explicit_bool_clear(rows, "referring_vet_report_sent")
        discharge_clear = _explicit_bool_clear(rows, "discharge_clear")

        if _has_procedure(rows) and consent_clear is False:
            _gate(gates, case_id, "red", "consent_gate", "Procedure blocked: consent not clear", "Explicit consentStatus is not clear for this referral pathway.", _state_rows(rows, "consent_status"))
        elif _has_procedure(rows) and consent_clear is None and not _has_clear(rows, CONSENT_TERMS):
            _gate(gates, case_id, "red", "consent_gate", "Procedure blocked: consent not clear", "No clear consent block is recorded for this referral pathway.", procedure_rows, "text_fallback")

        if _has_procedure(rows) and estimate_clear is False:
            _gate(gates, case_id, "red", "estimate_gate", "Procedure blocked: estimate not clear", "Explicit estimateStatus is not clear for this referral pathway.", _state_rows(rows, "estimate_status"))
        elif _has_procedure(rows) and estimate_clear is None and not _has_clear(rows, ESTIMATE_TERMS):
            _gate(gates, case_id, "red", "estimate_gate", "Procedure blocked: estimate not clear", "No clear estimate/cost approval is recorded for this referral pathway.", procedure_rows, "text_fallback")

        if insurance_open is True:
            _gate(gates, case_id, "amber", "insurance_gate", "Insurance/admin issue open", "Explicit insuranceStatus is not clear.", _state_rows(rows, "insurance_status"))
        elif insurance_open is None:
            insurance_blockers = _blocked_rows(rows, INSURANCE_TERMS)
            if insurance_blockers:
                _gate(gates, case_id, "amber", "insurance_gate", "Insurance/admin issue open", "Insurance, claim, estimate, or payment work still carries a blocker.", insurance_blockers, "text_fallback")

        if _has_procedure(rows) and pharmacy_open is True:
            _gate(gates, case_id, "red", "pharmacy_gate", "Procedure blocked: pharmacy not ready", "Explicit pharmacyReady is false.", _state_rows(rows, "pharmacy_ready"))
        elif _has_procedure(rows) and pharmacy_open is None:
            pharmacy_blockers = _blocked_rows(rows, PHARMACY_TERMS)
            if pharmacy_blockers:
                _gate(gates, case_id, "red", "pharmacy_gate", "Procedure blocked: pharmacy not ready", "Medication, contrast, anaesthesia or discharge medication task is not ready.", pharmacy_blockers, "text_fallback")

        if _has_discharge(rows) and owner_updated is False:
            _gate(gates, case_id, "red", "owner_update_gate", "Discharge blocked: owner update missing", "Explicit ownerUpdated is false.", _state_rows(rows, "owner_updated"))
        elif _has_discharge(rows) and owner_updated is None and not _has_clear(rows, OWNER_UPDATE_TERMS):
            _gate(gates, case_id, "red", "owner_update_gate", "Discharge blocked: owner update missing", "No clear owner/client update is recorded before discharge.", discharge_rows, "text_fallback")

        if _has_discharge(rows) and report_sent is False:
            _gate(gates, case_id, "amber", "referring_vet_report_gate", "Case cannot close: referring-vet report missing", "Explicit referringVetReportSent is false.", _state_rows(rows, "referring_vet_report_sent"))
        elif _has_discharge(rows) and report_sent is None and not _has_clear(rows, REFERRING_VET_TERMS):
            _gate(gates, case_id, "amber", "referring_vet_report_gate", "Case cannot close: referring-vet report missing", "No clear referring-vet report/letter sent state is recorded.", discharge_rows, "text_fallback")

        if _has_discharge(rows) and discharge_clear is False:
            _gate(gates, case_id, "red", "discharge_clear_gate", "Discharge not cleared", "Explicit dischargeClear is false.", _state_rows(rows, "discharge_clear"))

        owner_update_blockers = _blocked_rows(rows, OWNER_UPDATE_TERMS)
        report_blockers = _blocked_rows(rows, REFERRING_VET_TERMS)
        if owner_update_blockers:
            _gate(gates, case_id, "amber", "owner_update_blocker", "Owner/client update still blocked", "Owner/client communication has an unresolved blocker.", owner_update_blockers, "text_fallback")
        if report_blockers:
            _gate(gates, case_id, "amber", "referring_vet_report_blocker", "Referring-vet report still blocked", "Referral report/letter has an unresolved blocker.", report_blockers, "text_fallback")

    severity_order = {"red": 0, "amber": 1, "green": 2}
    gates.sort(key=lambda item: (severity_order.get(str(item.get("severity")), 9), str(item.get("caseId")), str(item.get("type"))))
    return {"gates": gates, "count": len(gates)}

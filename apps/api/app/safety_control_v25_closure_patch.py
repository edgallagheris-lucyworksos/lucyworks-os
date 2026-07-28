from __future__ import annotations

from app import safety_control_v25_service as service

_ORIGINAL_REVIEW_CLOSURE = service.review_closure


def review_closure_with_findings(session, record, auth, data):
    root_cause_supplied = data.get("rootCause") is not None
    controls_supplied = bool(data.get("recurrenceControls"))
    if root_cause_supplied or controls_supplied:
        before = service.sensitive_record_dict(record)
        if root_cause_supplied:
            root_cause = str(data.get("rootCause") or "").strip()
            if record.severity in {"red", "critical"} and len(root_cause) < 12:
                from fastapi import HTTPException

                raise HTTPException(status_code=400, detail="rootCause must meaningfully explain the failure")
            record.root_cause = root_cause or None
        if controls_supplied:
            record.recurrence_controls = [
                str(item).strip()
                for item in data.get("recurrenceControls", [])
                if str(item).strip()
            ]
        record.version += 1
        record.updated_at = service.utc_now()
        session.add(record)
        service.create_decision(
            session,
            record,
            auth,
            decision_type="investigation_findings",
            decision="recorded",
            reason=str(data.get("reason") or "Investigation findings recorded for independent review"),
            previous_state=before,
            result_state=service.sensitive_record_dict(record),
        )
    return _ORIGINAL_REVIEW_CLOSURE(session, record, auth, data)


service.review_closure = review_closure_with_findings

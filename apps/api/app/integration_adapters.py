from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class IntegrationAction:
    action_type: str
    action: str
    compliance_domain: str
    risk_level: str
    patient_case_id: str | None
    referral_episode_id: str | None
    state: dict[str, Any]


class IntegrationAdapter(Protocol):
    integration_type: str

    def normalise(self, message_type: str, payload: dict[str, Any]) -> list[IntegrationAction]: ...


def _patient(payload: dict[str, Any]) -> str | None:
    return payload.get("patient_case_id") or payload.get("patientCaseId")


def _episode(payload: dict[str, Any]) -> str | None:
    return payload.get("referral_episode_id") or payload.get("referralEpisodeId")


def _data(payload: dict[str, Any]) -> dict[str, Any]:
    value = payload.get("data")
    return value if isinstance(value, dict) else payload


class PIMSAdapter:
    integration_type = "pims"

    def normalise(self, message_type: str, payload: dict[str, Any]) -> list[IntegrationAction]:
        data = _data(payload)
        risk = "red" if message_type in {"patient.flagged", "referral.cancelled", "consent.withdrawn"} else "amber"
        return [IntegrationAction(
            action_type="evidence",
            action=f"PIMS {message_type.replace('.', ' ')} received",
            compliance_domain="patient_record",
            risk_level=risk,
            patient_case_id=_patient(payload),
            referral_episode_id=_episode(payload),
            state=data,
        )]


class ImagingAdapter:
    integration_type = "imaging"

    def normalise(self, message_type: str, payload: dict[str, Any]) -> list[IntegrationAction]:
        data = _data(payload)
        if message_type in {"service.status", "imaging.service_status"}:
            status = str(data.get("operational_status") or data.get("status") or "available").lower()
            return [IntegrationAction(
                action_type="service_status",
                action=f"imaging service set to {status}",
                compliance_domain="service_availability",
                risk_level="green" if status == "available" else "red",
                patient_case_id=None,
                referral_episode_id=None,
                state=data,
            )]
        severity = str(data.get("severity") or "amber").lower()
        is_critical = severity in {"critical", "red", "life_threatening"} or bool(data.get("critical"))
        return [IntegrationAction(
            action_type="critical_result" if is_critical else "evidence",
            action="critical imaging result received" if is_critical else f"imaging {message_type.replace('.', ' ')} received",
            compliance_domain="diagnostics",
            risk_level="red" if is_critical else "amber",
            patient_case_id=_patient(payload),
            referral_episode_id=_episode(payload),
            state=data,
        )]


class LaboratoryAdapter:
    integration_type = "laboratory"

    def normalise(self, message_type: str, payload: dict[str, Any]) -> list[IntegrationAction]:
        data = _data(payload)
        severity = str(data.get("severity") or "amber").lower()
        is_critical = severity in {"critical", "red", "life_threatening"} or bool(data.get("critical"))
        return [IntegrationAction(
            action_type="critical_result" if is_critical else "evidence",
            action="critical laboratory result received" if is_critical else f"laboratory {message_type.replace('.', ' ')} received",
            compliance_domain="diagnostics",
            risk_level="red" if is_critical else "amber",
            patient_case_id=_patient(payload),
            referral_episode_id=_episode(payload),
            state=data,
        )]


class HRAdapter:
    integration_type = "hr"

    def normalise(self, message_type: str, payload: dict[str, Any]) -> list[IntegrationAction]:
        data = _data(payload)
        status = str(data.get("status") or data.get("availability") or "changed").lower()
        red_states = {"unavailable", "suspended", "fatigued", "over_limit", "absent"}
        return [IntegrationAction(
            action_type="evidence",
            action=f"HR workforce status received: {status}",
            compliance_domain="workforce",
            risk_level="red" if status in red_states else "amber",
            patient_case_id=None,
            referral_episode_id=None,
            state=data,
        )]


ADAPTERS: dict[str, IntegrationAdapter] = {
    "pims": PIMSAdapter(),
    "imaging": ImagingAdapter(),
    "laboratory": LaboratoryAdapter(),
    "lab": LaboratoryAdapter(),
    "hr": HRAdapter(),
}


def adapter_for(integration_type: str) -> IntegrationAdapter:
    key = integration_type.lower().strip()
    if key not in ADAPTERS:
        raise ValueError(f"unsupported integration type: {integration_type}")
    return ADAPTERS[key]

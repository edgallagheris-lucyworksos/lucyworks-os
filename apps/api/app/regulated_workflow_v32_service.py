from __future__ import annotations

from dataclasses import dataclass


WRITTEN_ESTIMATE_THRESHOLD_PENCE = 50_000
MAX_UPDATE_TRIGGER_PENCE = 50_000
UPDATE_TRIGGER_PERCENT = 0.20


@dataclass(frozen=True)
class EstimateRuleResult:
    written_estimate_required: bool
    written_update_required: bool
    previous_upper_total_pence: int | None
    current_upper_total_pence: int
    increase_pence: int
    increase_percent: float | None
    update_threshold_pence: int | None
    trigger_reason: str


def evaluate_estimate_rules(*, current_upper_total_pence: int, previous_upper_total_pence: int | None) -> EstimateRuleResult:
    if current_upper_total_pence < 0:
        raise ValueError("estimate total cannot be negative")

    written_estimate_required = current_upper_total_pence >= WRITTEN_ESTIMATE_THRESHOLD_PENCE
    increase_pence = 0
    increase_percent: float | None = None
    update_threshold_pence: int | None = None
    written_update_required = False
    trigger_reason = "written_estimate_threshold" if written_estimate_required else "none"

    if previous_upper_total_pence is not None and previous_upper_total_pence > 0:
        increase_pence = max(0, current_upper_total_pence - previous_upper_total_pence)
        increase_percent = increase_pence / previous_upper_total_pence
        update_threshold_pence = min(
            round(previous_upper_total_pence * UPDATE_TRIGGER_PERCENT),
            MAX_UPDATE_TRIGGER_PENCE,
        )
        written_update_required = increase_pence >= update_threshold_pence and increase_pence > 0
        if written_update_required:
            trigger_reason = "estimate_increase_20_percent_or_500_gbp"

    return EstimateRuleResult(
        written_estimate_required=written_estimate_required,
        written_update_required=written_update_required,
        previous_upper_total_pence=previous_upper_total_pence,
        current_upper_total_pence=current_upper_total_pence,
        increase_pence=increase_pence,
        increase_percent=increase_percent,
        update_threshold_pence=update_threshold_pence,
        trigger_reason=trigger_reason,
    )

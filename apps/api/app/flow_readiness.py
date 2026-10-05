from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Iterable


class ConstraintKind(StrEnum):
    HARD = "hard"
    OPERATIONAL = "operational"
    PREFERENCE = "preference"


@dataclass(frozen=True)
class ConstraintCheck:
    constraint_id: str
    kind: ConstraintKind
    satisfied: bool
    reason: str
    resolution: str | None = None


@dataclass(frozen=True)
class ReadinessResult:
    ready: bool
    hard_blockers: tuple[ConstraintCheck, ...]
    operational_warnings: tuple[ConstraintCheck, ...]
    preference_costs: tuple[ConstraintCheck, ...]

    @property
    def blocker_count(self) -> int:
        return len(self.hard_blockers)

    @property
    def has_warnings(self) -> bool:
        return bool(self.operational_warnings or self.preference_costs)


def evaluate_readiness(checks: Iterable[ConstraintCheck]) -> ReadinessResult:
    """Evaluate all known constraints without hiding downstream blockers.

    Hard constraints determine READY/BLOCKED. Operational rules and preferences
    remain visible so the recovery engine can compare otherwise feasible plans.
    """
    failed = tuple(check for check in checks if not check.satisfied)
    hard = tuple(check for check in failed if check.kind is ConstraintKind.HARD)
    operational = tuple(check for check in failed if check.kind is ConstraintKind.OPERATIONAL)
    preferences = tuple(check for check in failed if check.kind is ConstraintKind.PREFERENCE)
    return ReadinessResult(
        ready=not hard,
        hard_blockers=hard,
        operational_warnings=operational,
        preference_costs=preferences,
    )

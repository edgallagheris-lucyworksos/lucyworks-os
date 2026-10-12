"""Read-only, bounded recovery suggestions for explicit resource/staff collisions.

These are candidate schedule changes, NOT clinically authorised or fully validated
plans. Dependency propagation and hard-rule readiness must be rechecked before use.
"""
from __future__ import annotations

from dataclasses import dataclass, replace

from app.flow_hospital_state import HospitalState, Collision, FlowBlock, detect_collisions


@dataclass(frozen=True)
class RecoveryCandidate:
    moved_block_id: str
    new_start_minute: int
    delay_minutes: int
    resulting_state: HospitalState
    remaining_collisions: tuple[Collision, ...]
    status: str = "requires_human_review"


def propose_collision_resolutions(state: HospitalState) -> tuple[RecoveryCandidate, ...]:
    """Generate all one-move, forward-only collision resolutions.

    No arbitrary candidate-count cap. This is a first-stage local repair search,
    not a proof of global optimality or clinical feasibility.
    """
    suggestions: dict[tuple[str, int], RecoveryCandidate] = {}
    for collision in detect_collisions(state):
        left = state.block(collision.left_block_id)
        right = state.block(collision.right_block_id)
        for moving, anchor in ((left, right), (right, left)):
            if moving.start_minute >= anchor.end_minute:
                continue
            new_start = anchor.end_minute
            if new_start <= moving.start_minute:
                continue
            moved = replace(moving, start_minute=new_start)
            candidate_state = state.replace_block(moved)
            key = (moving.id, new_start)
            suggestions[key] = RecoveryCandidate(
                moved_block_id=moving.id,
                new_start_minute=new_start,
                delay_minutes=new_start - moving.start_minute,
                resulting_state=candidate_state,
                remaining_collisions=detect_collisions(candidate_state),
            )
    return tuple(sorted(
        suggestions.values(),
        key=lambda candidate: (
            len(candidate.remaining_collisions),
            candidate.delay_minutes,
            candidate.moved_block_id,
        ),
    ))

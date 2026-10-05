from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Iterable


@dataclass(frozen=True)
class FlowBlock:
    id: str
    start_minute: int
    duration_minutes: int
    episode_ref: str | None = None
    staff_ref: str | None = None
    resource_ref: str | None = None
    depends_on: tuple[str, ...] = ()

    @property
    def end_minute(self) -> int:
        return self.start_minute + self.duration_minutes


@dataclass(frozen=True)
class HospitalState:
    blocks: tuple[FlowBlock, ...]

    def block(self, block_id: str) -> FlowBlock:
        for item in self.blocks:
            if item.id == block_id:
                return item
        raise KeyError(block_id)

    def replace_block(self, updated: FlowBlock) -> "HospitalState":
        return HospitalState(tuple(updated if item.id == updated.id else item for item in self.blocks))


@dataclass(frozen=True)
class Disruption:
    block_id: str
    delay_minutes: int
    reason: str


@dataclass(frozen=True)
class Impact:
    block_id: str
    cause_block_id: str
    reason: str
    earliest_start_minute: int
    delay_minutes: int


@dataclass(frozen=True)
class Collision:
    kind: str
    left_block_id: str
    right_block_id: str
    ref: str


@dataclass(frozen=True)
class PropagationResult:
    state: HospitalState
    impacts: tuple[Impact, ...]
    collisions: tuple[Collision, ...]


def _overlap(left: FlowBlock, right: FlowBlock) -> bool:
    return left.start_minute < right.end_minute and right.start_minute < left.end_minute


def detect_collisions(state: HospitalState) -> tuple[Collision, ...]:
    collisions: list[Collision] = []
    blocks = sorted(state.blocks, key=lambda item: (item.start_minute, item.id))
    for index, left in enumerate(blocks):
        for right in blocks[index + 1:]:
            if not _overlap(left, right):
                continue
            if left.resource_ref and left.resource_ref == right.resource_ref:
                collisions.append(Collision("resource_overlap", left.id, right.id, left.resource_ref))
            if left.staff_ref and left.staff_ref == right.staff_ref:
                collisions.append(Collision("staff_overlap", left.id, right.id, left.staff_ref))
    return tuple(collisions)


def apply_disruption(state: HospitalState, disruption: Disruption) -> PropagationResult:
    if disruption.delay_minutes < 0:
        raise ValueError("delay_minutes must be non-negative")

    source = state.block(disruption.block_id)
    updated = state.replace_block(replace(source, duration_minutes=source.duration_minutes + disruption.delay_minutes))
    impacts: list[Impact] = []
    queue = [source.id]
    seen: set[tuple[str, str]] = set()

    while queue:
        cause_id = queue.pop(0)
        cause = updated.block(cause_id)
        for candidate in updated.blocks:
            if cause_id not in candidate.depends_on:
                continue
            edge = (cause_id, candidate.id)
            if edge in seen:
                continue
            seen.add(edge)
            earliest = max(candidate.start_minute, cause.end_minute)
            delay = earliest - candidate.start_minute
            if delay <= 0:
                continue
            shifted = replace(candidate, start_minute=earliest)
            updated = updated.replace_block(shifted)
            impacts.append(Impact(
                block_id=candidate.id,
                cause_block_id=cause_id,
                reason=f"dependency {cause_id} now ends at {cause.end_minute}",
                earliest_start_minute=earliest,
                delay_minutes=delay,
            ))
            queue.append(candidate.id)

    return PropagationResult(updated, tuple(impacts), detect_collisions(updated))

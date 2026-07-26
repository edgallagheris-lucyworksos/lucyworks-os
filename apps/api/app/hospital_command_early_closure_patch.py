from __future__ import annotations

from typing import Any

from sqlmodel import Session

from app import hospital_command_routes as routes
from app.hospital_command_hardening import EARLY_CLOSURE_PHASES
from app.hospital_ops_models import CanonicalEpisodeState

_previous_guard = routes.evaluate_guard


def evaluate_guard(session: Session, episode: CanonicalEpisodeState, target_phase: str) -> dict[str, Any]:
    result = _previous_guard(session, episode, target_phase)
    if target_phase == "closed" and episode.phase in EARLY_CLOSURE_PHASES:
        result["blockers"] = [item for item in result.get("blockers", []) if item.get("code") != "referral_acceptance"]
        result["canTransition"] = not result["blockers"]
        result["earlyClosure"] = True
    return result


routes.evaluate_guard = evaluate_guard

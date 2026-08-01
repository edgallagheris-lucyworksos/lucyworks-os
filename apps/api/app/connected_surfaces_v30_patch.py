from __future__ import annotations

from datetime import date
from typing import Any

from sqlmodel import Session, select

import app.hospital_master_board_v11_routes as board_routes
import app.hospital_ops_service as hospital_ops_service
from app.hospital_ops_models import BoardChangeEvent, CanonicalEpisodeState


_original_board_snapshot = board_routes.board_snapshot


def _row(row: Any) -> dict[str, Any]:
    return row.model_dump(mode="json")


def board_snapshot_v30(session: Session, premises_ref: str, operational_date: date) -> dict[str, Any]:
    board = _original_board_snapshot(session, premises_ref, operational_date)
    episodes = session.exec(
        select(CanonicalEpisodeState)
        .where(CanonicalEpisodeState.premises_ref == premises_ref)
        .order_by(CanonicalEpisodeState.urgency.desc(), CanonicalEpisodeState.updated_at)
    ).all()
    canonical = [_row(row) for row in episodes[:250]]
    placed_refs = {
        item.get("episodeRef")
        for item in board.get("blocks", [])
        if item.get("episodeRef")
    }
    changes = session.exec(
        select(BoardChangeEvent)
        .where(
            BoardChangeEvent.premises_ref == premises_ref,
            BoardChangeEvent.operational_date == operational_date,
            BoardChangeEvent.entity_type == "canonical_episode",
        )
        .order_by(BoardChangeEvent.created_at.desc())
    ).all()
    board["canonicalEpisodes"] = canonical
    board["unplacedEpisodes"] = [
        item for item in canonical
        if item.get("status") == "active" and item.get("episode_ref") not in placed_refs
    ]
    board["recentCanonicalChanges"] = [_row(row) for row in changes[:100]]
    board.setdefault("summary", {})
    board["summary"]["canonicalEpisodeCount"] = len(canonical)
    board["summary"]["unplacedEpisodeCount"] = len(board["unplacedEpisodes"])
    board["connectedOperationalProofVersion"] = "v30"
    return board


board_routes.board_snapshot = board_snapshot_v30
hospital_ops_service.board_snapshot = board_snapshot_v30

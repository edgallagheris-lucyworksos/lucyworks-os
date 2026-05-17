from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.database import get_session
from app.episode_state_machine import state_machine_spec, transition_episode, transition_guard
from app.models import Episode

router = APIRouter()


@router.get("/api/episode-state-machine")
def get_episode_state_machine():
    return state_machine_spec()


@router.get("/api/episodes/{episode_ref}/state-guard/{target_state}")
def get_episode_transition_guard(episode_ref: str, target_state: str, session: Session = Depends(get_session)):
    episode = session.exec(select(Episode).where(Episode.episode_ref == episode_ref)).first()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")
    return transition_guard(session, episode, target_state)


@router.post("/api/episodes/{episode_ref}/transition")
def post_episode_transition(episode_ref: str, payload: dict, session: Session = Depends(get_session)):
    target_state = payload.get("target_state")
    actor_name = payload.get("actor_name", "LucyWorks OS")
    reason = payload.get("reason", "")
    if not target_state:
        raise HTTPException(status_code=400, detail="target_state is required")
    result = transition_episode(session, episode_ref, target_state, actor_name, reason)
    if not result.get("ok") and result.get("error") == "episode_not_found":
        raise HTTPException(status_code=404, detail="Episode not found")
    return result

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from app.database import get_session
from app.models import Episode
from app.ops_engine import WORKFLOW, department_for_episode, evaluate_transition, transition_episode

router = APIRouter()


class TransitionPayload(BaseModel):
    target_state: str
    actor_name: str = "Ops Engine"
    note: str | None = None


@router.get("/api/ops-engine/workflows")
def workflows():
    return {"workflows": WORKFLOW}


@router.get("/api/ops-engine/episodes/{episode_ref}")
def episode_engine_state(episode_ref: str, session: Session = Depends(get_session)):
    episode = session.exec(select(Episode).where(Episode.episode_ref == episode_ref)).first()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")
    department = department_for_episode(episode)
    states = WORKFLOW[department]
    current = episode.current_phase or states[0]
    return {
        "episode_ref": episode_ref,
        "department": department,
        "current_state": current,
        "allowed_next_states": states,
        "episode": episode,
    }


@router.post("/api/ops-engine/episodes/{episode_ref}/evaluate")
def evaluate_episode_transition(episode_ref: str, payload: TransitionPayload, session: Session = Depends(get_session)):
    episode = session.exec(select(Episode).where(Episode.episode_ref == episode_ref)).first()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")
    return evaluate_transition(session, episode, payload.target_state)


@router.post("/api/ops-engine/episodes/{episode_ref}/transition")
def transition_episode_endpoint(episode_ref: str, payload: TransitionPayload, session: Session = Depends(get_session)):
    result = transition_episode(session, episode_ref, payload.target_state, payload.actor_name, payload.note)
    if not result.get("allowed"):
        raise HTTPException(status_code=409, detail=result)
    return result

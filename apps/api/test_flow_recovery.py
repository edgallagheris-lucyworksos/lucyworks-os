from app.flow_hospital_state import FlowBlock, HospitalState
from app.flow_recovery import propose_collision_resolutions


def test_recovery_exposes_forward_moves_without_autonomous_changes() -> None:
    state = HospitalState((
        FlowBlock("case-a", 540, 60, "a", "nurse-a", "MRI"),
        FlowBlock("case-b", 570, 45, "b", "nurse-b", "MRI"),
    ))
    plans = propose_collision_resolutions(state)
    assert plans
    assert any(not plan.remaining_collisions for plan in plans)
    assert all(plan.status == "requires_human_review" for plan in plans)
    assert state.block("case-b").start_minute == 570


def test_uncontested_state_requires_no_repair() -> None:
    state = HospitalState((
        FlowBlock("case-a", 540, 30, resource_ref="CT"),
        FlowBlock("case-b", 600, 30, resource_ref="CT"),
    ))
    assert propose_collision_resolutions(state) == ()


def test_one_move_does_not_claim_global_feasibility() -> None:
    state = HospitalState((
        FlowBlock("a", 540, 60, resource_ref="MRI"),
        FlowBlock("b", 550, 60, resource_ref="MRI"),
        FlowBlock("c", 620, 60, resource_ref="MRI"),
    ))
    plans = propose_collision_resolutions(state)
    assert plans
    assert all(plan.status == "requires_human_review" for plan in plans)

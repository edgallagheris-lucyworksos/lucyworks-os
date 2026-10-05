from app.flow_hospital_state import Disruption, FlowBlock, HospitalState, apply_disruption


def test_overrun_propagates_through_dependency_chain() -> None:
    state = HospitalState((
        FlowBlock("mri", 540, 60, "case-1", "nurse-1", "MRI"),
        FlowBlock("recovery", 600, 30, "case-1", "nurse-1", "RECOVERY-1", ("mri",)),
        FlowBlock("review", 630, 15, "case-1", "clinician-1", "CONSULT-1", ("recovery",)),
    ))

    result = apply_disruption(state, Disruption("mri", 25, "scanner delay"))

    assert result.state.block("mri").end_minute == 625
    assert result.state.block("recovery").start_minute == 625
    assert result.state.block("review").start_minute == 655
    assert [(impact.block_id, impact.delay_minutes) for impact in result.impacts] == [
        ("recovery", 25),
        ("review", 25),
    ]


def test_propagated_delay_exposes_downstream_resource_collision() -> None:
    state = HospitalState((
        FlowBlock("ct-case-a", 600, 30, "case-a", "nurse-a", "CT"),
        FlowBlock("recovery-a", 630, 30, "case-a", "nurse-a", "RECOVERY-1", ("ct-case-a",)),
        FlowBlock("recovery-b", 650, 30, "case-b", "nurse-b", "RECOVERY-1"),
    ))

    result = apply_disruption(state, Disruption("ct-case-a", 20, "induction overrun"))

    assert result.state.block("recovery-a").start_minute == 650
    assert any(
        collision.kind == "resource_overlap"
        and {collision.left_block_id, collision.right_block_id} == {"recovery-a", "recovery-b"}
        for collision in result.collisions
    )


def test_unrelated_work_does_not_move() -> None:
    state = HospitalState((
        FlowBlock("theatre", 540, 60, "case-a", "nurse-a", "THEATRE-1"),
        FlowBlock("ct", 570, 30, "case-b", "nurse-b", "CT"),
    ))

    result = apply_disruption(state, Disruption("theatre", 30, "procedure complexity"))

    assert result.state.block("ct").start_minute == 570
    assert result.impacts == ()


def test_negative_delay_is_rejected() -> None:
    state = HospitalState((FlowBlock("mri", 540, 60),))

    try:
        apply_disruption(state, Disruption("mri", -5, "invalid"))
    except ValueError as exc:
        assert str(exc) == "delay_minutes must be non-negative"
    else:
        raise AssertionError("negative disruption should fail")

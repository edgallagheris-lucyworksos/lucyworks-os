from app.flow_readiness import ConstraintCheck, ConstraintKind, evaluate_readiness


def test_hard_constraint_blocks_and_all_failures_remain_visible() -> None:
    result = evaluate_readiness([
        ConstraintCheck("consent", ConstraintKind.HARD, True, "consent valid"),
        ConstraintCheck(
            "anaesthetist",
            ConstraintKind.HARD,
            False,
            "anaesthetist unavailable until 10:40",
            "wait until 10:40 or assign another authorised anaesthetist",
        ),
        ConstraintCheck(
            "long-procedure-cutoff",
            ConstraintKind.OPERATIONAL,
            False,
            "long procedure would start after local 14:30 cutoff",
            "senior operational override required",
        ),
        ConstraintCheck(
            "surgeon-order",
            ConstraintKind.PREFERENCE,
            False,
            "recovery option changes preferred surgeon order",
        ),
    ])

    assert result.ready is False
    assert result.blocker_count == 1
    assert result.hard_blockers[0].constraint_id == "anaesthetist"
    assert result.operational_warnings[0].constraint_id == "long-procedure-cutoff"
    assert result.preference_costs[0].constraint_id == "surgeon-order"


def test_operational_rule_does_not_become_fake_safety_blocker() -> None:
    result = evaluate_readiness([
        ConstraintCheck(
            "local-sequencing-rule",
            ConstraintKind.OPERATIONAL,
            False,
            "hospital prefers imaging before ward round",
        ),
    ])

    assert result.ready is True
    assert result.blocker_count == 0
    assert result.has_warnings is True


def test_no_failed_constraints_is_ready() -> None:
    result = evaluate_readiness([
        ConstraintCheck("consent", ConstraintKind.HARD, True, "consent valid"),
        ConstraintCheck("skill", ConstraintKind.HARD, True, "required skill present"),
        ConstraintCheck("resource", ConstraintKind.HARD, True, "resource available"),
    ])

    assert result.ready is True
    assert result.blocker_count == 0
    assert result.has_warnings is False

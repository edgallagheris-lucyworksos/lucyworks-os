from app.workflow_action_routes import OperationalRecordPayload

print("\n--- RUNNING OPERATIONAL ACTION SMOKE TEST ---\n")

payload = OperationalRecordPayload(
    action="assign",
    target_id="arrival-triage",
    target_label="Arrival / triage",
    target_type="flow-stage",
    owner_role="triage_owner",
    blocker="untriaged",
    next_action="assign triage owner",
)

assert payload.action == "assign"
assert payload.target_id == "arrival-triage"
assert payload.target_type == "flow-stage"
assert payload.owner_role == "triage_owner"

print("\n--- OPERATIONAL ACTION TEST PASSED ---\n")

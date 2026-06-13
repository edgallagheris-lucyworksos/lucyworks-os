from app.queue_routes import QueuePayload

print("\n--- RUNNING QUEUE WORK ITEM SMOKE TEST ---\n")

payload = QueuePayload(
    title="Escalate: ECC stabilisation",
    role="clinical_director_or_ops_manager",
    queue="escalation_queue",
    urgency="urgent",
    detail="Route blocker to senior queue",
)

assert payload.role == "clinical_director_or_ops_manager"
assert payload.queue == "escalation_queue"
assert payload.urgency == "urgent"

print("\n--- QUEUE WORK ITEM TEST PASSED ---\n")

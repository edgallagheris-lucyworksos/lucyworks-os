from app.queue_routes import QueuePayload
from app.staff_assignment import acceptable_staff_roles

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

senior_roles = acceptable_staff_roles(payload.role, payload.queue)
assert "clinical_director" in senior_roles
assert "ops_manager" in senior_roles
assert "hospital_manager" in senior_roles

bed_roles = acceptable_staff_roles("ward_or_icu_lead", "bed_capacity_queue")
assert "icu_nurse" in bed_roles
assert "ward_nurse" in bed_roles
assert "medical_nurse_lead" in bed_roles

imaging_roles = acceptable_staff_roles("imaging_lead", "imaging_queue")
assert "radiographer" in imaging_roles
assert "radiologist" in imaging_roles
assert "imaging_lead" in imaging_roles

theatre_roles = acceptable_staff_roles("theatre_lead", "theatre_queue")
assert "theatre_nurse_lead" in theatre_roles
assert "theatre_technician" in theatre_roles
assert "anaesthesia_nurse" in theatre_roles

print("\n--- QUEUE WORK ITEM TEST PASSED ---\n")

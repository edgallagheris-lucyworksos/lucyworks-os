from app.canonical_modules import flow_route_for_urgency, pulse_status_from_scores, rota_match

print("\n--- RUNNING CANONICAL MODULE SMOKE TEST ---\n")

assert flow_route_for_urgency("red") == "Escalate to Ethics"
assert flow_route_for_urgency("amber") == "Review by Senior Nurse"
assert flow_route_for_urgency("green") == "Assign to Vet Team"

assert pulse_status_from_scores([90, 85, 88]) == "CRITICAL"
assert pulse_status_from_scores([61, 62, 60]) == "WARNING"
assert pulse_status_from_scores([20, 45, 55]) == "NORMAL"
assert pulse_status_from_scores([]) == "NORMAL"

staff = [
    {"staff_name": "Lucy", "certifications": ["ECC", "nurse"], "availability": ["2026-05-07"]},
    {"staff_name": "Tom", "certifications": ["vet", "surgery"], "availability": ["2026-05-08"]},
]
assert rota_match(staff, "2026-05-07", "ECC") == "Lucy"
assert rota_match(staff, "2026-05-08", "surgery") == "Tom"
assert rota_match(staff, "2026-05-07", "anaesthesia") == "No Match Found"

print("\n--- CANONICAL MODULE TEST PASSED ---\n")

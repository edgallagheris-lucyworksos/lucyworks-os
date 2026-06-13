export type OperationalDestination = {
  action: string;
  label: string;
  destinationRole: string;
  destinationQueue: string;
  urgency: "routine" | "soon" | "urgent" | "critical";
  reason: string;
};

export const operationalDestinations: OperationalDestination[] = [
  { action: "assign", label: "Assign owner", destinationRole: "owning_service_or_shift_lead", destinationQueue: "role_queue", urgency: "soon", reason: "puts the item into the correct role queue with ownership" },
  { action: "escalate", label: "Escalate", destinationRole: "clinical_director_or_ops_manager", destinationQueue: "escalation_queue", urgency: "urgent", reason: "senior decision needed or unsafe delay" },
  { action: "resolve", label: "Resolve", destinationRole: "current_owner", destinationQueue: "audit_and_completion", urgency: "routine", reason: "closes the blocker and records the decision" },
  { action: "handover", label: "Handover", destinationRole: "receiving_role", destinationQueue: "handover_queue", urgency: "soon", reason: "moves responsibility to the next team or shift" },
  { action: "hold", label: "Hold", destinationRole: "ops_manager", destinationQueue: "capacity_hold_queue", urgency: "urgent", reason: "protects theatre, bed, imaging or procedure capacity" },
  { action: "request_review", label: "Request review", destinationRole: "clinical_owner_or_senior", destinationQueue: "review_queue", urgency: "soon", reason: "asks the right clinician or lead to review before movement" },
  { action: "owner_update", label: "Owner update", destinationRole: "admin_or_service_clinician", destinationQueue: "owner_comms_queue", urgency: "soon", reason: "creates a communication task for owner update or consent" },
  { action: "insurance", label: "Insurance action", destinationRole: "insurance_admin", destinationQueue: "insurance_queue", urgency: "soon", reason: "routes estimate, cover or pre-authorisation work" },
  { action: "pharmacy", label: "Pharmacy task", destinationRole: "pharmacy_owner", destinationQueue: "pharmacy_queue", urgency: "soon", reason: "routes meds, discharge meds or stock task" },
  { action: "bed_request", label: "Bed request", destinationRole: "ward_or_icu_lead", destinationQueue: "bed_capacity_queue", urgency: "urgent", reason: "requests ICU, recovery or ward destination" },
  { action: "imaging_request", label: "Imaging request", destinationRole: "imaging_lead", destinationQueue: "imaging_queue", urgency: "soon", reason: "requests MRI, CT, X-ray, ultrasound or report owner" },
  { action: "theatre_request", label: "Theatre request", destinationRole: "theatre_lead", destinationQueue: "theatre_queue", urgency: "urgent", reason: "requests theatre, kit, anaesthesia or recovery readiness" },
];

export function destinationFor(action: string) {
  return operationalDestinations.find((item) => item.action === action) || operationalDestinations[0];
}

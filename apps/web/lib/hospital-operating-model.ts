export type OperatingUnitType =
  | "theatre"
  | "imaging"
  | "xray"
  | "lab"
  | "pharmacy"
  | "insurance"
  | "ward"
  | "icu"
  | "recovery"
  | "triage"
  | "reception"
  | "owner_comms"
  | "stock"
  | "equipment"
  | "governance";

export type OperatingUnit = {
  id: string;
  label: string;
  type: OperatingUnitType;
  route: string;
  ownerRole: string;
  tracks: string[];
  blockers: string[];
};

export const theatreUnits: OperatingUnit[] = Array.from({ length: 11 }, (_, index) => ({
  id: `theatre-${index + 1}`,
  label: `Theatre ${index + 1}`,
  type: "theatre",
  route: "/resources",
  ownerRole: "theatre_lead",
  tracks: ["case", "procedure", "anaesthesia", "nurse", "kit", "room_state", "recovery_destination"],
  blockers: ["anaesthesia_cover", "kit_missing", "consent_missing", "room_turnover", "recovery_capacity", "staffing_gap"],
}));

export const coreOperatingUnits: OperatingUnit[] = [
  ...theatreUnits,
  {
    id: "mri",
    label: "MRI",
    type: "imaging",
    route: "/resources",
    ownerRole: "imaging_lead",
    tracks: ["case", "slot", "anaesthesia", "contrast", "report_owner", "machine_state"],
    blockers: ["anaesthesia_cover", "machine_blocked", "consent_missing", "result_owner_missing", "handover_missing"],
  },
  {
    id: "ct",
    label: "CT",
    type: "imaging",
    route: "/resources",
    ownerRole: "imaging_lead",
    tracks: ["case", "slot", "contrast", "report_owner", "machine_state"],
    blockers: ["machine_blocked", "contrast_decision", "result_owner_missing", "handover_missing"],
  },
  {
    id: "xray",
    label: "X-ray",
    type: "xray",
    route: "/resources",
    ownerRole: "imaging_nurse",
    tracks: ["case", "room", "sedation", "report_owner", "machine_state"],
    blockers: ["room_unavailable", "sedation_cover", "result_owner_missing"],
  },
  {
    id: "lab",
    label: "Laboratory",
    type: "lab",
    route: "/lucy-clinical",
    ownerRole: "lab_owner",
    tracks: ["sample", "case", "test", "result", "review_owner", "turnaround_time"],
    blockers: ["sample_missing", "result_pending", "review_owner_missing", "machine_issue"],
  },
  {
    id: "pharmacy",
    label: "Pharmacy",
    type: "pharmacy",
    route: "/lucy-pharm",
    ownerRole: "pharmacy_owner",
    tracks: ["drug", "stock", "controlled_item", "discharge_meds", "prescriber", "collection"],
    blockers: ["stock_low", "prescription_missing", "controlled_drug_check", "discharge_meds_incomplete"],
  },
  {
    id: "insurance",
    label: "Insurance / pre-authorisation",
    type: "insurance",
    route: "/lucy-comms",
    ownerRole: "admin",
    tracks: ["case", "estimate", "pre_auth", "claim_status", "owner_contact", "payment_risk"],
    blockers: ["pre_auth_pending", "estimate_not_sent", "owner_decision_pending", "claim_info_missing"],
  },
  {
    id: "icu",
    label: "ICU",
    type: "icu",
    route: "/resources",
    ownerRole: "icu_nurse",
    tracks: ["bed", "oxygen", "patient", "obs_due", "nurse", "recovery_acceptance"],
    blockers: ["bed_full", "oxygen_full", "nurse_unavailable", "obs_overdue", "handover_missing"],
  },
  {
    id: "recovery",
    label: "Recovery",
    type: "recovery",
    route: "/resources",
    ownerRole: "recovery_nurse",
    tracks: ["patient", "procedure", "anaesthesia", "temperature", "pain_score", "destination"],
    blockers: ["space_unavailable", "nurse_unavailable", "temperature_low", "handover_missing"],
  },
  {
    id: "ward",
    label: "Ward",
    type: "ward",
    route: "/my-shift",
    ownerRole: "ward_nurse",
    tracks: ["bed", "patient", "obs_due", "meds", "discharge_status", "owner_update"],
    blockers: ["bed_full", "obs_overdue", "meds_missing", "discharge_blocked", "owner_update_due"],
  },
  {
    id: "triage",
    label: "Triage / reception intake",
    type: "triage",
    route: "/flow",
    ownerRole: "triage_owner",
    tracks: ["arrival", "urgency", "presenting_signs", "owner", "assigned_service", "waiting_time"],
    blockers: ["untriaged", "red_case_waiting", "service_owner_missing", "owner_info_missing"],
  },
  {
    id: "owner-comms",
    label: "Owner communications",
    type: "owner_comms",
    route: "/lucy-comms",
    ownerRole: "admin",
    tracks: ["owner", "case", "callback_due", "consent", "estimate", "complaint_risk"],
    blockers: ["callback_overdue", "consent_missing", "estimate_missing", "complaint_risk"],
  },
  {
    id: "stock-equipment",
    label: "Stock / equipment readiness",
    type: "equipment",
    route: "/resources",
    ownerRole: "ops_manager",
    tracks: ["kit", "stock", "procedure", "supplier", "sterile_status", "location"],
    blockers: ["kit_missing", "stock_low", "sterile_pack_missing", "supplier_delay"],
  },
  {
    id: "governance",
    label: "Governance / audit",
    type: "governance",
    route: "/lucy-gov",
    ownerRole: "clinical_director",
    tracks: ["decision", "actor", "time", "case", "conflict", "resolution"],
    blockers: ["decision_unowned", "conflict_unresolved", "audit_gap", "safety_issue_unclosed"],
  },
];

export function operatingUnitsByRoute(route: string) {
  return coreOperatingUnits.filter((unit) => unit.route === route);
}

export function operatingUnitById(id: string) {
  return coreOperatingUnits.find((unit) => unit.id === id);
}

export type BvsPublicPathway = {
  id: string;
  label: string;
  publicEvidence: string;
  intakeFields: string[];
  lucyModule: string;
  queueTargets: string[];
  blockers: string[];
};

export const bvsPublicPathways: BvsPublicPathway[] = [
  {
    id: "urgent-referral",
    label: "Urgent referral",
    publicEvidence: "BVS public referral page directs urgent referrals to phone the hospital directly.",
    intakeFields: ["referring vet", "practice", "patient", "species", "urgency", "service requested", "problem outline"],
    lucyModule: "LucyFlow",
    queueTargets: ["escalation_queue", "role_queue"],
    blockers: ["urgent call not owned", "service owner missing", "triage priority unclear"],
  },
  {
    id: "routine-referral",
    label: "Routine referral form",
    publicEvidence: "BVS public referral form collects owner details, patient details, referral request, case urgency, history and referring vet details.",
    intakeFields: ["owner details", "insurance company", "patient species", "breed", "age", "weight", "travel/import history", "referral service", "case urgency", "history files", "referring vet details"],
    lucyModule: "LucyFlow",
    queueTargets: ["role_queue", "owner_comms_queue", "insurance_queue"],
    blockers: ["history missing", "owner contact missing", "service not selected", "insurance detail missing"],
  },
  {
    id: "request-advice",
    label: "Request advice",
    publicEvidence: "BVS request advice page says the form is for non-urgent matters and urgent queries should be phoned through.",
    intakeFields: ["patient details", "species", "advice service", "case urgency", "problem outline", "history", "referring vet contact windows"],
    lucyModule: "LucyClinical",
    queueTargets: ["clinical_owner_or_senior", "role_queue"],
    blockers: ["clinical findings incomplete", "call-back window missing", "wrong urgent route"],
  },
  {
    id: "owner-consult-journey",
    label: "Owner consultation journey",
    publicEvidence: "BVS pet journey page describes preparation, consultation, diagnostic/treatment plan, estimate, consent, tests/procedure, owner update and discharge.",
    intakeFields: ["fasting status", "clinical history", "exam", "diagnostic plan", "treatment plan", "estimate", "consent", "procedure duration", "owner update", "discharge plan"],
    lucyModule: "LucyComms",
    queueTargets: ["owner_comms_queue", "clinical_owner_or_senior"],
    blockers: ["consent missing", "estimate not accepted", "owner update due", "emergency interruption"],
  },
  {
    id: "insurance-payment",
    label: "Insurance and payment",
    publicEvidence: "BVS payment page describes direct claims, indirect claims, pre-authorisation, insurance documentation, deposits for uninsured pets and dedicated insurance support.",
    intakeFields: ["insurance company", "policy details", "claim form", "pre-authorisation", "direct or indirect claim", "excess", "deposit", "balance"],
    lucyModule: "LucyComms",
    queueTargets: ["insurance_queue", "owner_comms_queue"],
    blockers: ["pre-authorisation pending", "claim form missing", "deposit required", "shortfall risk"],
  },
  {
    id: "aftercare-discharge",
    label: "Aftercare and discharge",
    publicEvidence: "BVS pet journey and FAQ pages describe discharge planning, ongoing management, report to primary vet and possible follow-up.",
    intakeFields: ["care plan", "primary vet report", "follow-up owner", "medication", "collection", "payment state"],
    lucyModule: "LucyPharm",
    queueTargets: ["pharmacy_queue", "owner_comms_queue", "role_queue"],
    blockers: ["meds not ready", "report not sent", "owner collection not ready", "payment unresolved"],
  },
  {
    id: "teer-cardiology",
    label: "TEER cardiology pathway",
    publicEvidence: "BVS public pages advertise minimally invasive mitral valve transcatheter edge-to-edge repair for dogs with advanced degenerative mitral valve disease.",
    intakeFields: ["cardiology referral", "advanced MVD", "suitability assessment", "owner consent", "anaesthesia plan", "interventional plan", "post-procedure monitoring"],
    lucyModule: "LucyClinical",
    queueTargets: ["clinical_owner_or_senior", "theatre_queue", "bed_capacity_queue", "owner_comms_queue"],
    blockers: ["suitability unclear", "anaesthesia risk", "interventional slot", "post-procedure monitoring destination"],
  },
  {
    id: "professional-education",
    label: "Vet professional / CPD pathway",
    publicEvidence: "BVS website includes CPD Events and vet professional routes in its public navigation.",
    intakeFields: ["event", "vet professional", "topic", "attendance", "follow-up"],
    lucyModule: "LucyKnowledge",
    queueTargets: ["role_queue"],
    blockers: ["event owner missing", "follow-up not logged"],
  },
];

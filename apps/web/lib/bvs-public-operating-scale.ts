export type BvsPublicWorkforceGroup = {
  id: string;
  label: string;
  evidence: string;
  lucyRoles: string[];
  queueTargets: string[];
};

export type BvsPublicCapacityArea = {
  id: string;
  label: string;
  publicCapacity: number | null;
  publicCapacityNote: string;
  tracks: string[];
};

export const bvsPublicTeamScale = {
  sourceDate: "2026-06-13",
  publicMinimumTeamSize: 100,
  publicNote: "BVS states that the hospital has over 100 highly skilled professionals. Public pages list many named clinicians, nurses, radiographers, PCAs, admin and support staff, but do not publish a full rota or live staffing count.",
};

export const bvsPublicWorkforceGroups: BvsPublicWorkforceGroup[] = [
  { id: "consultants-specialists", label: "Consultants and veterinary specialists", evidence: "Team page lists consultants across anaesthesia, diagnostic imaging, dermatology, dentistry, surgery, internal medicine, neurology, oncology, ophthalmology, orthopaedics and cardiology.", lucyRoles: ["clinical_director", "clinician", "specialist", "service_clinician"], queueTargets: ["clinical_owner_or_senior", "owning_service_or_shift_lead"] },
  { id: "residents-interns", label: "Residents and interns", evidence: "Team page lists residents and interns across diagnostic imaging, neurology, surgery, anaesthesia, internal medicine, oncology and rotating internship.", lucyRoles: ["resident", "intern", "clinician"], queueTargets: ["receiving_role", "clinical_owner_or_senior"] },
  { id: "nurses", label: "Registered and specialist nurses", evidence: "Team page lists ICU, anaesthesia, theatre, medicine, oncology, dermatology, ophthalmology, neurology, feline, orthopaedic and senior nursing roles.", lucyRoles: ["nurse", "rvn", "icu_nurse", "ward_nurse", "theatre_nurse", "specialist_nurse"], queueTargets: ["ward_or_icu_lead", "theatre_lead", "pharmacy_owner", "receiving_role"] },
  { id: "diagnostic-team", label: "Radiologists and radiographers", evidence: "Diagnostic imaging page describes on-site specialist radiologists, professional radiographers and experienced nurses.", lucyRoles: ["radiologist", "radiographer", "imaging_lead", "imaging_nurse"], queueTargets: ["imaging_lead", "clinical_owner_or_senior"] },
  { id: "radiotherapy-team", label: "Radiotherapy team", evidence: "Team and facilities pages list therapeutic radiographers and radiotherapy/cancer treatment using a linear accelerator.", lucyRoles: ["therapeutic_radiographer", "oncology", "radiotherapy"], queueTargets: ["clinical_owner_or_senior", "imaging_lead"] },
  { id: "pca-support", label: "Patient care assistants and support services", evidence: "Team page lists ICU PCA, laboratory PCA, internal medicine PCA, orthopaedics and neurology PCA and head support services nurse.", lucyRoles: ["pca", "support_services", "laboratory_pca"], queueTargets: ["receiving_role", "bed_capacity_queue"] },
  { id: "admin-client-care", label: "Admin, reception, referral and insurance", evidence: "Team page lists administrator, receptionist, referral coordinator and insurance administrator roles; pet journey page identifies a dedicated insurance department.", lucyRoles: ["admin", "reception", "referral_coordinator", "insurance_admin", "client_care"], queueTargets: ["owner_comms_queue", "insurance_queue"] },
  { id: "hospital-management", label: "Hospital management and facilities", evidence: "Team page lists hospital managers and facilities manager roles.", lucyRoles: ["hospital_manager", "ops_manager", "facilities_manager"], queueTargets: ["escalation_queue", "capacity_hold_queue"] },
];

export const bvsPublicCapacityAreas: BvsPublicCapacityArea[] = [
  { id: "canine-wing", label: "Canine wing / dog wards and kennels", publicCapacity: null, publicCapacityNote: "Public site confirms separate dog facilities and kennel areas but does not publish bed/kennel count.", tracks: ["species", "kennel", "ward bed", "owner update", "discharge blocker"] },
  { id: "feline-wing", label: "Feline wing / cat wards and kennels", publicCapacity: null, publicCapacityNote: "Public site confirms separate cat facilities and specialist feline wing but does not publish bed/kennel count.", tracks: ["species", "kennel", "ward bed", "stress separation", "discharge blocker"] },
  { id: "isolation", label: "Isolation units", publicCapacity: null, publicCapacityNote: "Public site confirms isolation units but does not publish isolation capacity.", tracks: ["infection risk", "PPE", "species", "separate housing", "nursing owner"] },
  { id: "icu-critical-care", label: "ICU / emergency and critical care", publicCapacity: null, publicCapacityNote: "Public ECC page confirms intensive care capability and constant monitoring equipment but does not publish ICU bed count.", tracks: ["triage", "stabilisation", "monitoring", "oxygen", "senior review", "handover"] },
  { id: "day-patients", label: "Day patient diagnostic/procedure flow", publicCapacity: null, publicCapacityNote: "Pet journey page says some pets may stay for the entire day and emergency cases may take priority; no public concurrent day-patient capacity is published.", tracks: ["consult", "consent", "estimate", "diagnostics", "owner update", "collection"] },
  { id: "operating-theatres", label: "Operating theatres", publicCapacity: 5, publicCapacityNote: "Facilities page publicly states five new spacious operating theatres.", tracks: ["procedure", "anaesthesia", "kit", "room state", "recovery destination"] },
  { id: "interventional-suite", label: "Interventional suite", publicCapacity: 1, publicCapacityNote: "Facilities page publicly states a dedicated interventional suite with fluoroscopy.", tracks: ["fluoroscopy", "procedure", "anaesthesia", "kit", "recovery destination"] },
  { id: "consulting-rooms", label: "Dog and cat consulting rooms", publicCapacity: null, publicCapacityNote: "Public site confirms separate dog and cat consulting rooms but does not publish room count.", tracks: ["species", "consultant", "owner", "history", "plan", "consent"] },
];

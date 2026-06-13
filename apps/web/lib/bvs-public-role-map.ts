export type BvsPublicRoleMapEntry = {
  id: string;
  publicRoleGroup: string;
  publicEvidence: string;
  lucyRole: string;
  queueTarget: string;
  escalationEligible: boolean;
  canReceiveDirectWork: boolean;
};

export const bvsPublicRoleMap: BvsPublicRoleMapEntry[] = [
  { id: "clinical-director", publicRoleGroup: "Clinical Director", publicEvidence: "BVS team page lists a Clinical Director.", lucyRole: "clinical_director", queueTarget: "escalation_queue", escalationEligible: true, canReceiveDirectWork: true },
  { id: "hospital-manager", publicRoleGroup: "Hospital Manager", publicEvidence: "BVS team page lists Hospital Manager roles.", lucyRole: "hospital_manager", queueTarget: "escalation_queue", escalationEligible: true, canReceiveDirectWork: true },
  { id: "service-heads", publicRoleGroup: "Heads of clinical departments", publicEvidence: "BVS team page lists heads for anaesthesia, diagnostic imaging, surgery, internal medicine, neurology, oncology and outpatient services.", lucyRole: "service_head", queueTarget: "clinical_owner_or_senior", escalationEligible: true, canReceiveDirectWork: true },
  { id: "consultants-specialists", publicRoleGroup: "Consultants and specialists", publicEvidence: "BVS lists consultants across the main referral disciplines.", lucyRole: "consultant_specialist", queueTarget: "clinical_owner_or_senior", escalationEligible: true, canReceiveDirectWork: true },
  { id: "residents-interns", publicRoleGroup: "Residents and interns", publicEvidence: "BVS lists residents and interns across multiple services.", lucyRole: "resident_or_intern", queueTarget: "receiving_role", escalationEligible: false, canReceiveDirectWork: true },
  { id: "head-surgical-services-nurse", publicRoleGroup: "Head Surgical Services Nurse", publicEvidence: "BVS team page lists a Head Surgical Services Nurse.", lucyRole: "theatre_nurse_lead", queueTarget: "theatre_queue", escalationEligible: true, canReceiveDirectWork: true },
  { id: "head-medical-services-nurse", publicRoleGroup: "Head Medical Services Nurse", publicEvidence: "BVS team page lists a Head Medical Services Nurse.", lucyRole: "medical_nurse_lead", queueTarget: "bed_capacity_queue", escalationEligible: true, canReceiveDirectWork: true },
  { id: "head-support-services-nurse", publicRoleGroup: "Head Support Services Nurse", publicEvidence: "BVS team page lists a Head Support Services Nurse.", lucyRole: "support_services_lead", queueTarget: "receiving_role", escalationEligible: true, canReceiveDirectWork: true },
  { id: "icu-nurses", publicRoleGroup: "ICU nurses and ICU PCA", publicEvidence: "BVS team page lists Senior ICU nurse, ICU nurses and ICU PCA roles.", lucyRole: "icu_team", queueTarget: "bed_capacity_queue", escalationEligible: false, canReceiveDirectWork: true },
  { id: "theatre-anaesthesia", publicRoleGroup: "Anaesthesia nurses and theatre technicians", publicEvidence: "BVS team page lists anaesthesia nurses and theatre technician roles.", lucyRole: "theatre_anaesthesia_team", queueTarget: "theatre_queue", escalationEligible: false, canReceiveDirectWork: true },
  { id: "imaging-team", publicRoleGroup: "Diagnostic imaging consultants, radiographers and nurses", publicEvidence: "BVS diagnostic imaging page describes specialist radiologists, professional radiographers and experienced nurses.", lucyRole: "imaging_team", queueTarget: "imaging_queue", escalationEligible: true, canReceiveDirectWork: true },
  { id: "radiotherapy-team", publicRoleGroup: "Radiotherapy / therapeutic radiography team", publicEvidence: "BVS team page lists therapeutic radiographers and the facilities page lists a linear accelerator.", lucyRole: "radiotherapy_team", queueTarget: "imaging_queue", escalationEligible: false, canReceiveDirectWork: true },
  { id: "referral-admin", publicRoleGroup: "Referral coordinator and reception", publicEvidence: "BVS team page lists referral coordinator and referral receptionist roles.", lucyRole: "referral_admin", queueTarget: "role_queue", escalationEligible: false, canReceiveDirectWork: true },
  { id: "insurance-admin", publicRoleGroup: "Insurance administrator", publicEvidence: "BVS team page and payment page identify insurance administration/department functions.", lucyRole: "insurance_admin", queueTarget: "insurance_queue", escalationEligible: false, canReceiveDirectWork: true },
  { id: "facilities", publicRoleGroup: "Facilities manager", publicEvidence: "BVS team page lists a Facilities Manager.", lucyRole: "facilities_manager", queueTarget: "capacity_hold_queue", escalationEligible: true, canReceiveDirectWork: true },
];

export function bvsEscalationRoleGroups() {
  return bvsPublicRoleMap.filter((entry) => entry.escalationEligible);
}

export function bvsRolesForQueue(queueTarget: string) {
  return bvsPublicRoleMap.filter((entry) => entry.queueTarget === queueTarget);
}

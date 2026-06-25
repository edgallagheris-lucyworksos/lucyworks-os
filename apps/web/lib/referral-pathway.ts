import { procedureForWork, pharmacyLabels, type ProcedureCatalogueItem } from "@/lib/clinical-catalogue";
import type { ScheduledWorkBlock } from "@/lib/day-control-work";

type GenerateReferralPathwayArgs = {
  caseId: string;
  subject: string;
  startTime: string;
  procedureText: string;
  ownerRole?: string;
  ownerName?: string;
};

function addMinutes(time: string, minutes: number) {
  const [h, m] = time.split(":").map(Number);
  const total = h * 60 + m + minutes;
  return `${String(Math.floor(total / 60)).padStart(2, "0")}:${String(total % 60).padStart(2, "0")}`;
}

function block(args: { id: string; time: string; lane: ScheduledWorkBlock["lane"]; what: string; who: string; where: string; how: string; blocker?: string; next: string; subject: string; caseId: string; duration: number; ownerRole?: string; ownerName?: string; resourceName?: string }): ScheduledWorkBlock {
  return { id: args.id, time: args.time, lane: args.lane, what: args.what, who: args.who, where: args.where, how: args.how, status: args.blocker ? "amber" : "green", blocker: args.blocker || "none", next: args.next, route: "/hospital-board", subject: args.subject, durationMinutes: args.duration, generatedFrom: "referral-pathway", episodeRef: args.caseId, assignedRole: args.ownerRole, assignedStaffName: args.ownerName, resourceName: args.resourceName };
}

function procedureStep(item: ProcedureCatalogueItem, args: GenerateReferralPathwayArgs): ScheduledWorkBlock[] {
  const pathway = args.caseId;
  const t0 = args.startTime;
  const pharmacy = pharmacyLabels(item.pharmacyRefs).join(" / ");
  return [
    block({ id: `${pathway}-triage`, time: t0, lane: "arrival", what: "Referral triage", who: "triage nurse", where: "front desk / triage", how: "confirm referral reason and urgency", next: "clinical review", subject: args.subject, caseId: pathway, duration: 15, ownerRole: "triage nurse" }),
    block({ id: `${pathway}-consent-estimate`, time: addMinutes(t0, 15), lane: "insurance", what: "Consent and estimate gate", who: "admin", where: "admin queue", how: "confirm consent, estimate, insurance and owner understanding", blocker: "consent / estimate must be confirmed before procedure", next: item.label, subject: args.subject, caseId: pathway, duration: item.referralAdminMinutes || 20, ownerRole: "admin" }),
    block({ id: `${pathway}-procedure`, time: addMinutes(t0, 45), lane: item.area.includes("theatre") ? "rooms" : item.area.includes("imaging") ? "imaging" : "consult", what: item.label, who: item.accountableRole, where: item.resourceType, how: item.safetyChecks.join(" / "), next: "handover / recovery / owner update", subject: args.subject, caseId: pathway, duration: item.defaultMinutes, ownerRole: args.ownerRole || item.accountableRole, ownerName: args.ownerName, resourceName: item.resourceType }),
    block({ id: `${pathway}-pharmacy`, time: addMinutes(t0, 45), lane: "supply", what: "Pharmacy preparation", who: "pharmacy", where: "pharmacy", how: pharmacy || "no medication dependency", blocker: item.pharmacyRefs.length ? "pharmacy dependency must be prepared" : undefined, next: "confirm medication availability", subject: args.subject, caseId: pathway, duration: 15, ownerRole: "pharmacy" }),
    block({ id: `${pathway}-handover`, time: addMinutes(t0, 45 + item.defaultMinutes), lane: "nursing", what: "Clinical handover", who: item.supportRoles.join(" / ") || "nurse", where: "handover point", how: "handover case, risks, plan and next location", next: "owner update", subject: args.subject, caseId: pathway, duration: item.handoverMinutes, ownerRole: "nurse" }),
    block({ id: `${pathway}-owner-update`, time: addMinutes(t0, 60 + item.defaultMinutes), lane: "client", what: "Owner update", who: "clinician / admin", where: "client contact", how: "update owner, document decision, confirm plan", blocker: "owner update required before closure", next: "report to referring vet", subject: args.subject, caseId: pathway, duration: item.referralAdminMinutes || 20, ownerRole: "admin" }),
    block({ id: `${pathway}-referring-vet-report`, time: addMinutes(t0, 90 + item.defaultMinutes), lane: "client", what: "Report to referring vet", who: "clinician", where: "admin / clinical notes", how: "complete report and discharge communication", blocker: "referral report not sent", next: "close referral episode", subject: args.subject, caseId: pathway, duration: 20, ownerRole: "clinician" }),
  ];
}

export function generateReferralPathway(args: GenerateReferralPathwayArgs): ScheduledWorkBlock[] {
  const item = procedureForWork(args.procedureText) || procedureForWork("consult");
  if (!item) return [];
  return procedureStep(item, args);
}

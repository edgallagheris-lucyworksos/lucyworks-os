export type DayControlLane = "intake" | "client" | "decision" | "nursing" | "rooms" | "imaging" | "care" | "supply" | "breaks";
export type DayControlStatus = "red" | "amber" | "green" | "blue";

export type ScheduledWorkBlock = {
  id: string;
  time: string;
  lane: DayControlLane;
  what: string;
  who: string;
  where: string;
  how: string;
  status: DayControlStatus;
  blocker: string;
  next: string;
  route: string;
  subject?: string;
  durationMinutes?: number;
  generatedFrom?: string;
};

export type ProcedureTemplate = {
  key: string;
  label: string;
  resource: string;
  prepMinutes: number;
  procedureMinutes: number;
  recoveryMinutes: number;
  updateMinutes: number;
  staffRoles: string[];
};

export type ScheduledCase = {
  id: string;
  subject: string;
  templateKey: string;
  start: string;
  owner: string;
  status: DayControlStatus;
  blocker?: string;
};

export const dayControlLanes: { key: DayControlLane; label: string; purpose: string }[] = [
  { key: "intake", label: "Front door", purpose: "New work entering the hospital." },
  { key: "client", label: "Client contact", purpose: "Calls, consent, estimates and updates." },
  { key: "decision", label: "Clinical decision", purpose: "Review, signoff, plans and escalation." },
  { key: "nursing", label: "Nursing / PCA", purpose: "Hands-on work, handover and support tasks." },
  { key: "rooms", label: "Rooms", purpose: "Room order, readiness and turnover." },
  { key: "imaging", label: "Imaging", purpose: "Slots, queue priority and reporting ownership." },
  { key: "care", label: "Care area", purpose: "Beds, handover, cover and destination capacity." },
  { key: "supply", label: "Supply", purpose: "Stock, signoff and release blockers." },
  { key: "breaks", label: "Breaks / welfare", purpose: "Break cover, overload and safe staffing." },
];

export const procedureTemplates: ProcedureTemplate[] = [
  { key: "mri", label: "MRI workup", resource: "MRI", prepMinutes: 30, procedureMinutes: 60, recoveryMinutes: 45, updateMinutes: 15, staffRoles: ["imaging lead", "nurse", "clinician"] },
  { key: "ct", label: "CT workup", resource: "CT", prepMinutes: 20, procedureMinutes: 30, recoveryMinutes: 30, updateMinutes: 15, staffRoles: ["imaging lead", "nurse", "clinician"] },
  { key: "theatre_major", label: "Major procedure", resource: "Theatre", prepMinutes: 45, procedureMinutes: 150, recoveryMinutes: 90, updateMinutes: 15, staffRoles: ["surgeon", "nurse", "PCA", "anaesthesia"] },
  { key: "theatre_minor", label: "Short procedure", resource: "Theatre", prepMinutes: 30, procedureMinutes: 60, recoveryMinutes: 60, updateMinutes: 15, staffRoles: ["clinician", "nurse", "PCA"] },
  { key: "discharge", label: "Discharge package", resource: "Client contact", prepMinutes: 15, procedureMinutes: 30, recoveryMinutes: 0, updateMinutes: 15, staffRoles: ["nurse", "client contact"] },
];

export const scheduledCases: ScheduledCase[] = [
  { id: "case-001", subject: "Bailey", templateKey: "mri", start: "08:00", owner: "imaging lead", status: "amber", blocker: "report owner not set" },
  { id: "case-002", subject: "Milo", templateKey: "theatre_major", start: "09:00", owner: "surgical lead", status: "red", blocker: "staff cover thin" },
  { id: "case-003", subject: "Poppy", templateKey: "ct", start: "10:15", owner: "imaging lead", status: "green" },
  { id: "case-004", subject: "Luna", templateKey: "discharge", start: "12:30", owner: "nurse", status: "amber", blocker: "client update pending" },
  { id: "case-005", subject: "Oscar", templateKey: "theatre_minor", start: "13:45", owner: "clinician", status: "amber", blocker: "room readiness pending" },
];

function quarterHourSlots(startHour: number, endHour: number) {
  const slots: string[] = [];
  for (let hour = startHour; hour <= endHour; hour += 1) {
    for (const minute of [0, 15, 30, 45]) {
      if (hour === endHour && minute > 0) continue;
      slots.push(`${String(hour).padStart(2, "0")}:${String(minute).padStart(2, "0")}`);
    }
  }
  return slots;
}

function toMinutes(time: string) {
  const [hour, minute] = time.split(":").map(Number);
  return hour * 60 + minute;
}

function fromMinutes(total: number) {
  const hour = Math.floor(total / 60);
  const minute = total % 60;
  return `${String(hour).padStart(2, "0")}:${String(minute).padStart(2, "0")}`;
}

function templateFor(key: string) {
  const template = procedureTemplates.find((item) => item.key === key);
  if (!template) throw new Error(`Missing procedure template: ${key}`);
  return template;
}

function routeForLane(lane: DayControlLane) {
  if (lane === "intake") return "/lucy-intake";
  if (lane === "client") return "/flow";
  if (lane === "decision") return "/my-shift";
  if (lane === "nursing") return "/my-shift";
  if (lane === "rooms") return "/theatre";
  if (lane === "imaging") return "/imaging";
  if (lane === "care") return "/icu-wards";
  if (lane === "supply") return "/lucy-pharm";
  return "/rota";
}

function makeBlock(caseItem: ScheduledCase, template: ProcedureTemplate, offset: number, lane: DayControlLane, what: string, who: string, how: string, durationMinutes: number, blocker = "none"): ScheduledWorkBlock {
  const time = fromMinutes(toMinutes(caseItem.start) + offset);
  return {
    id: `${caseItem.id}-${lane}-${offset}`,
    time,
    lane,
    what,
    who,
    where: template.resource,
    how,
    status: blocker !== "none" ? "amber" : caseItem.status,
    blocker,
    next: blocker !== "none" ? "clear blocker" : "continue planned flow",
    route: routeForLane(lane),
    subject: caseItem.subject,
    durationMinutes,
    generatedFrom: template.key,
  };
}

function expandCase(caseItem: ScheduledCase): ScheduledWorkBlock[] {
  const template = templateFor(caseItem.templateKey);
  const procedureStart = template.prepMinutes;
  const recoveryStart = template.prepMinutes + template.procedureMinutes;
  const updateStart = recoveryStart + template.recoveryMinutes;
  const blocker = caseItem.blocker || "none";
  return [
    makeBlock(caseItem, template, 0, "nursing", `${caseItem.subject}: prep`, template.staffRoles.join(" + "), "prepare and safety check", template.prepMinutes, blocker === "staff cover thin" ? blocker : "none"),
    makeBlock(caseItem, template, procedureStart, template.resource === "MRI" || template.resource === "CT" ? "imaging" : "rooms", `${caseItem.subject}: ${template.label}`, caseItem.owner, "run planned slot", template.procedureMinutes, blocker === "room readiness pending" ? blocker : "none"),
    makeBlock(caseItem, template, recoveryStart, "care", `${caseItem.subject}: recovery / handover`, "care area lead", "recover and hand over", template.recoveryMinutes, "none"),
    makeBlock(caseItem, template, updateStart, "client", `${caseItem.subject}: short update`, "client contact", "send generated update", template.updateMinutes, blocker === "client update pending" || blocker === "report owner not set" ? blocker : "none"),
    makeBlock(caseItem, template, updateStart, "decision", `${caseItem.subject}: decision check`, caseItem.owner, "confirm next action", 15, blocker === "report owner not set" ? blocker : "none"),
  ].filter((block) => block.durationMinutes !== 0);
}

export const dayControlTimes = quarterHourSlots(7, 20);

export const scheduledWorkBlocks: ScheduledWorkBlock[] = scheduledCases.flatMap(expandCase);

export function blocksFor(time: string, lane: DayControlLane) {
  return scheduledWorkBlocks.filter((block) => block.time === time && block.lane === lane);
}

export function pressureBlocks() {
  return scheduledWorkBlocks.filter((block) => block.status === "red" || block.status === "amber" || block.blocker !== "none");
}

export function totalMinutesScheduled() {
  return scheduledWorkBlocks.reduce((total, block) => total + (block.durationMinutes || 0), 0);
}

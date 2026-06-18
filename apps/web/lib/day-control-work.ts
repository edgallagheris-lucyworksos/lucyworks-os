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

export const dayControlTimes = ["07:00", "08:00", "09:00", "10:00", "11:00", "12:00", "13:00", "14:00", "15:00", "16:00"];

export const scheduledWorkBlocks: ScheduledWorkBlock[] = [
  { id: "dc-001", time: "08:00", lane: "intake", what: "New intake route", who: "coordinator", where: "front desk", how: "triage and assign", status: "red", blocker: "route not set", next: "send to correct service", route: "/lucy-intake" },
  { id: "dc-002", time: "09:00", lane: "client", what: "Client update", who: "client contact lead", where: "phone queue", how: "short generated update", status: "amber", blocker: "update not sent", next: "send client update", route: "/flow" },
  { id: "dc-003", time: "09:00", lane: "decision", what: "Plan review", who: "clinical lead", where: "decision queue", how: "review and signoff", status: "amber", blocker: "owner unclear", next: "assign decision owner", route: "/my-shift" },
  { id: "dc-004", time: "10:00", lane: "rooms", what: "Room readiness", who: "area support", where: "room", how: "ready check", status: "green", blocker: "none", next: "prepare next slot", route: "/theatre" },
  { id: "dc-005", time: "10:00", lane: "imaging", what: "Slot order", who: "imaging lead", where: "scan queue", how: "priority check", status: "amber", blocker: "priority unclear", next: "confirm priority", route: "/imaging" },
  { id: "dc-006", time: "11:00", lane: "care", what: "Capacity row", who: "area lead", where: "care area", how: "capacity check", status: "red", blocker: "destination full", next: "confirm movement plan", route: "/icu-wards" },
  { id: "dc-007", time: "12:00", lane: "breaks", what: "Break cover", who: "ops manager", where: "staff rota", how: "rebalance cover", status: "amber", blocker: "thin cover", next: "move safe support", route: "/rota" },
  { id: "dc-008", time: "13:00", lane: "supply", what: "Stock row", who: "area lead", where: "supply queue", how: "stock check", status: "amber", blocker: "low count", next: "request stock", route: "/lucy-pharm" },
  { id: "dc-009", time: "14:00", lane: "nursing", what: "Handover row", who: "senior role", where: "team task", how: "write plan", status: "amber", blocker: "plan missing", next: "write plan", route: "/my-shift" },
  { id: "dc-010", time: "15:00", lane: "client", what: "Release update", who: "client contact", where: "phone queue", how: "generated update", status: "amber", blocker: "final check", next: "clear priority items", route: "/flow" },
];

export function blocksFor(time: string, lane: DayControlLane) {
  return scheduledWorkBlocks.filter((block) => block.time === time && block.lane === lane);
}

export function pressureBlocks() {
  return scheduledWorkBlocks.filter((block) => block.status === "red" || block.status === "amber");
}

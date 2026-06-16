export type CanonicalArea = "theatre" | "imaging" | "care" | "supply" | "front-door" | "people";

export type CanonicalWorkStatus = "red" | "amber" | "green" | "blue";

export type CanonicalWorkItem = {
  id: string;
  area: CanonicalArea;
  item: string;
  patient: string;
  owner: string;
  status: CanonicalWorkStatus;
  blocker: string;
  next: string;
  due: string;
  route: string;
};

export const canonicalOperationalWork: CanonicalWorkItem[] = [
  { id: "theatre-001", area: "theatre", item: "Room order", patient: "slot", owner: "area lead", status: "amber", blocker: "readiness check", next: "confirm order", due: "08:30", route: "/flow" },
  { id: "theatre-002", area: "theatre", item: "Room reset", patient: "slot", owner: "support", status: "green", blocker: "none", next: "prepare next slot", due: "10:15", route: "/rooms" },
  { id: "theatre-003", area: "theatre", item: "Late slot", patient: "slot", owner: "lead", status: "red", blocker: "destination capacity", next: "confirm capacity", due: "14:00", route: "/resources" },
  { id: "imaging-001", area: "imaging", item: "Slot order", patient: "queue item", owner: "area lead", status: "amber", blocker: "priority unclear", next: "confirm priority", due: "09:00", route: "/flow" },
  { id: "imaging-002", area: "imaging", item: "Report row", patient: "queue item", owner: "reporting role", status: "red", blocker: "owner missing", next: "assign owner", due: "10:30", route: "/my-shift" },
  { id: "imaging-003", area: "imaging", item: "Reserve capacity", patient: "capacity", owner: "coordinator", status: "blue", blocker: "none", next: "keep reserve", due: "12:00", route: "/resources" },
  { id: "care-001", area: "care", item: "Capacity row", patient: "capacity", owner: "area lead", status: "red", blocker: "destination full", next: "confirm movement plan", due: "08:45", route: "/resources" },
  { id: "care-002", area: "care", item: "Handover row", patient: "team task", owner: "senior role", status: "amber", blocker: "plan missing", next: "write plan", due: "10:00", route: "/my-shift" },
  { id: "care-003", area: "care", item: "Cover row", patient: "staffing", owner: "ops manager", status: "amber", blocker: "thin cover", next: "rebalance rota", due: "15:30", route: "/rota" },
  { id: "supply-001", area: "supply", item: "Signoff queue", patient: "queue item", owner: "signing role", status: "red", blocker: "owner missing", next: "assign signoff", due: "09:30", route: "/my-shift" },
  { id: "supply-002", area: "supply", item: "Stock row", patient: "stock item", owner: "area lead", status: "amber", blocker: "low count", next: "request stock", due: "11:00", route: "/resources" },
  { id: "supply-003", area: "supply", item: "Release row", patient: "release item", owner: "area team", status: "amber", blocker: "final check", next: "clear priority items", due: "15:00", route: "/flow" },
  { id: "front-001", area: "front-door", item: "New intake", patient: "entry item", owner: "coordinator", status: "red", blocker: "triage route needed", next: "route to correct area", due: "now", route: "/lucy-intake" },
  { id: "people-001", area: "people", item: "Break cover", patient: "staffing", owner: "ops manager", status: "amber", blocker: "thin cover", next: "rebalance cover", due: "12:00", route: "/rota" },
];

export function workItemsForArea(area: CanonicalArea) {
  return canonicalOperationalWork.filter((item) => item.area === area);
}

export function highPressureWorkItems() {
  return canonicalOperationalWork.filter((item) => item.status === "red" || item.status === "amber");
}

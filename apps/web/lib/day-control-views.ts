import { scheduledWorkBlocks, type DayControlLane, type ScheduledWorkBlock } from "@/lib/day-control-work";

const STORAGE_KEY = "lucyworks.day-control.blocks.v1";

function currentBlocks(): ScheduledWorkBlock[] {
  if (typeof window === "undefined") return scheduledWorkBlocks;
  try {
    const saved = window.localStorage.getItem(STORAGE_KEY);
    return saved ? JSON.parse(saved) as ScheduledWorkBlock[] : scheduledWorkBlocks;
  } catch {
    return scheduledWorkBlocks;
  }
}

export function workRowsForLanes(lanes: DayControlLane[]) {
  return currentBlocks()
    .filter((block) => lanes.includes(block.lane))
    .map((block) => ({
      id: block.id,
      item: block.what,
      patient: block.subject || block.what,
      owner: block.who,
      status: block.status,
      blocker: block.blocker,
      next: block.next,
      due: block.time,
      route: block.route,
    }));
}

export function workRowsForLane(lane: DayControlLane) {
  return workRowsForLanes([lane]);
}

export function pressureRowsForLanes(lanes: DayControlLane[]) {
  return workRowsForLanes(lanes).filter((row) => row.status === "red" || row.status === "amber" || row.blocker !== "none");
}

import { scheduledWorkBlocks, type DayControlLane } from "@/lib/day-control-work";

export function workRowsForLanes(lanes: DayControlLane[]) {
  return scheduledWorkBlocks
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

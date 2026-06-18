import type { ScheduledWorkBlock } from "@/lib/day-control-work";

export type DayControlRiskLevel = "red" | "amber" | "blue";

export type DayControlRisk = {
  id: string;
  level: DayControlRiskLevel;
  title: string;
  detail: string;
  blockIds: string[];
};

function keyFor(block: ScheduledWorkBlock) {
  return `${block.time}-${block.where}`;
}

export function detectDayControlRisks(blocks: ScheduledWorkBlock[]): DayControlRisk[] {
  const risks: DayControlRisk[] = [];
  const byTimeAndPlace = new Map<string, ScheduledWorkBlock[]>();

  for (const block of blocks) {
    if (block.where && block.where !== "Reception" && block.where !== "Admin queue") {
      const key = keyFor(block);
      byTimeAndPlace.set(key, [...(byTimeAndPlace.get(key) || []), block]);
    }
    if (block.blocker !== "none") {
      risks.push({
        id: `blocker-${block.id}`,
        level: block.status === "red" ? "red" : "amber",
        title: `${block.time} ${block.what}`,
        detail: `Blocker: ${block.blocker}. Next: ${block.next}.`,
        blockIds: [block.id],
      });
    }
    if (block.lane === "client" && block.blocker !== "none") {
      risks.push({
        id: `update-${block.id}`,
        level: "amber",
        title: `Update risk: ${block.subject || block.what}`,
        detail: `A contact update is blocked or not ready. Next: ${block.next}.`,
        blockIds: [block.id],
      });
    }
    if (block.lane === "breaks" && block.blocker !== "none") {
      risks.push({
        id: `welfare-${block.id}`,
        level: "red",
        title: `Staff welfare pressure at ${block.time}`,
        detail: `Break or cover blocker: ${block.blocker}.`,
        blockIds: [block.id],
      });
    }
  }

  for (const [key, matching] of byTimeAndPlace.entries()) {
    if (matching.length > 1) {
      risks.push({
        id: `resource-clash-${key}`,
        level: "red",
        title: `Resource clash: ${key}`,
        detail: matching.map((block) => block.what).join(" / "),
        blockIds: matching.map((block) => block.id),
      });
    }
  }

  return risks;
}

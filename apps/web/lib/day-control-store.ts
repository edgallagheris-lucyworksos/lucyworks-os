"use client";

import { useEffect, useMemo, useState } from "react";
import type { OperationalActionType } from "@/lib/operational-actions";
import { scheduledWorkBlocks, type DayControlLane, type ScheduledWorkBlock } from "@/lib/day-control-work";

const STORAGE_KEY = "lucyworks.day-control.blocks.v1";

export function applyDayControlAction(block: ScheduledWorkBlock, action: OperationalActionType): ScheduledWorkBlock {
  if (action === "resolve") return { ...block, status: "green", blocker: "none", next: "complete or continue planned flow" };
  if (action === "hold") return { ...block, status: "blue", blocker: "on hold", next: "review hold reason" };
  if (action === "escalate") return { ...block, status: "red", blocker: block.blocker === "none" ? "escalated" : block.blocker, next: "senior review required" };
  if (action === "request_review") return { ...block, status: "amber", next: "review requested" };
  if (action === "assign") return { ...block, status: block.status === "red" ? "red" : "amber", next: "owner assigned" };
  if (action === "handover") return { ...block, status: "green", blocker: "none", next: "handover complete" };
  if (action === "owner_update") return { ...block, status: "green", blocker: "none", next: "update recorded" };
  return { ...block, status: "amber", next: `${action.replaceAll("_", " ")} requested` };
}

function loadBlocks() {
  if (typeof window === "undefined") return scheduledWorkBlocks;
  try {
    const saved = window.localStorage.getItem(STORAGE_KEY);
    return saved ? JSON.parse(saved) as ScheduledWorkBlock[] : scheduledWorkBlocks;
  } catch {
    return scheduledWorkBlocks;
  }
}

function saveBlocks(blocks: ScheduledWorkBlock[]) {
  if (typeof window === "undefined") return;
  try { window.localStorage.setItem(STORAGE_KEY, JSON.stringify(blocks)); } catch {}
}

export function useDayControlStore() {
  const [blocks, setBlocks] = useState<ScheduledWorkBlock[]>(scheduledWorkBlocks);

  useEffect(() => {
    setBlocks(loadBlocks());
  }, []);

  useEffect(() => {
    saveBlocks(blocks);
  }, [blocks]);

  function applyAction(blockId: string, action: OperationalActionType) {
    setBlocks((current) => current.map((block) => block.id === blockId ? applyDayControlAction(block, action) : block));
  }

  function resetBlocks() {
    setBlocks(scheduledWorkBlocks);
    if (typeof window !== "undefined") {
      try { window.localStorage.removeItem(STORAGE_KEY); } catch {}
    }
  }

  function rowsForLanes(lanes: DayControlLane[]) {
    return blocks
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

  const pressure = useMemo(() => blocks.filter((block) => block.status === "red" || block.status === "amber" || block.blocker !== "none"), [blocks]);
  const blocked = useMemo(() => blocks.filter((block) => block.blocker !== "none"), [blocks]);

  return { blocks, pressure, blocked, applyAction, resetBlocks, rowsForLanes };
}

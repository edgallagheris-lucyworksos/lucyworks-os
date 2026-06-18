"use client";

import { useEffect, useMemo, useState } from "react";
import type { OperationalActionType } from "@/lib/operational-actions";
import { scheduledWorkBlocks, type DayControlLane, type ScheduledWorkBlock } from "@/lib/day-control-work";

const STORAGE_KEY = "lucyworks.day-control.blocks.v1";
const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

export type DayControlAssignmentPatch = Pick<ScheduledWorkBlock, "assignedRole" | "assignedStaffId" | "assignedStaffName" | "resourceId" | "resourceName">;

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
  try { const saved = window.localStorage.getItem(STORAGE_KEY); return saved ? JSON.parse(saved) as ScheduledWorkBlock[] : scheduledWorkBlocks; } catch { return scheduledWorkBlocks; }
}
function saveBlocks(blocks: ScheduledWorkBlock[]) { if (typeof window === "undefined") return; try { window.localStorage.setItem(STORAGE_KEY, JSON.stringify(blocks)); } catch {} }
async function apiGetBlocks() { const response = await fetch(`${API_BASE}/api/day-control/blocks`); if (!response.ok) throw new Error("blocks request failed"); const data = await response.json(); return Array.isArray(data.blocks) ? data.blocks as ScheduledWorkBlock[] : []; }
async function apiReplaceBlocks(blocks: ScheduledWorkBlock[]) { await fetch(`${API_BASE}/api/day-control/blocks/bulk`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ blocks }) }); }
async function apiAction(blockId: string, action: OperationalActionType) { const response = await fetch(`${API_BASE}/api/day-control/blocks/${blockId}/actions`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ action, actor: "frontend" }) }); if (!response.ok) throw new Error("action request failed"); const data = await response.json(); return data.block as ScheduledWorkBlock; }
async function apiPatchBlock(blockId: string, patch: Partial<ScheduledWorkBlock>) { const response = await fetch(`${API_BASE}/api/day-control/blocks/${blockId}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(patch) }); if (!response.ok) throw new Error("patch request failed"); const data = await response.json(); return data.block as ScheduledWorkBlock; }

export function useDayControlStore() {
  const [blocks, setBlocks] = useState<ScheduledWorkBlock[]>(scheduledWorkBlocks);
  const [syncStatus, setSyncStatus] = useState<"local" | "api" | "offline">("local");

  useEffect(() => {
    let active = true;
    const localBlocks = loadBlocks();
    setBlocks(localBlocks);
    apiGetBlocks().then(async (apiBlocks) => {
      if (!active) return;
      if (apiBlocks.length) { setBlocks(apiBlocks); saveBlocks(apiBlocks); setSyncStatus("api"); }
      else { await apiReplaceBlocks(localBlocks); setSyncStatus("api"); }
    }).catch(() => { if (active) setSyncStatus("offline"); });
    return () => { active = false; };
  }, []);

  useEffect(() => { saveBlocks(blocks); }, [blocks]);

  function applyAction(blockId: string, action: OperationalActionType) {
    setBlocks((current) => current.map((block) => block.id === blockId ? applyDayControlAction(block, action) : block));
    apiAction(blockId, action).then((updated) => { setBlocks((current) => current.map((block) => block.id === blockId ? updated : block)); setSyncStatus("api"); }).catch(() => setSyncStatus("offline"));
  }

  function patchBlock(blockId: string, patch: Partial<ScheduledWorkBlock>) {
    setBlocks((current) => current.map((block) => block.id === blockId ? { ...block, ...patch } : block));
    apiPatchBlock(blockId, patch).then((updated) => { setBlocks((current) => current.map((block) => block.id === blockId ? updated : block)); setSyncStatus("api"); }).catch(() => setSyncStatus("offline"));
  }

  function assignBlock(blockId: string, patch: DayControlAssignmentPatch) { patchBlock(blockId, { ...patch, next: "assignment updated", status: "amber" }); }
  function clearAssignment(blockId: string) { patchBlock(blockId, { assignedRole: undefined, assignedStaffId: undefined, assignedStaffName: undefined, resourceId: undefined, resourceName: undefined, next: "assignment cleared", status: "amber" }); }

  function resetBlocks() {
    setBlocks(scheduledWorkBlocks);
    if (typeof window !== "undefined") { try { window.localStorage.removeItem(STORAGE_KEY); } catch {} }
    apiReplaceBlocks(scheduledWorkBlocks).then(() => setSyncStatus("api")).catch(() => setSyncStatus("offline"));
  }

  function rowsForLanes(lanes: DayControlLane[]) {
    return blocks.filter((block) => lanes.includes(block.lane)).map((block) => ({ id: block.id, item: block.what, patient: block.subject || block.what, owner: block.assignedStaffName || block.assignedRole || block.who, status: block.status, blocker: block.blocker, next: block.next, due: block.time, route: block.route }));
  }

  const pressure = useMemo(() => blocks.filter((block) => block.status === "red" || block.status === "amber" || block.blocker !== "none"), [blocks]);
  const blocked = useMemo(() => blocks.filter((block) => block.blocker !== "none"), [blocks]);
  return { blocks, pressure, blocked, applyAction, patchBlock, assignBlock, clearAssignment, resetBlocks, rowsForLanes, syncStatus };
}

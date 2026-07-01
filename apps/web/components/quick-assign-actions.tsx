"use client";

import { useEffect, useMemo, useState } from "react";
import type { ScheduledWorkBlock } from "@/lib/day-control-work";

type StaffOption = { id: number; name: string; role: string; area: string; active?: boolean };
type ResourceOption = { id: string; name: string; type: string; active?: boolean };
type PatchBlock = (blockId: string, patch: Partial<ScheduledWorkBlock>) => void;
type ClearBlock = (blockId: string) => void;

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

function textFor(block: ScheduledWorkBlock) {
  return `${block.assignedRole || ""} ${block.who || ""} ${block.what || ""} ${block.where || ""} ${block.how || ""} ${block.next || ""}`.toLowerCase();
}

function roleScore(staff: StaffOption, block: ScheduledWorkBlock) {
  const text = textFor(block);
  const role = `${staff.role || ""} ${staff.area || ""}`.toLowerCase();
  let score = 0;
  if (text.includes(staff.role.toLowerCase())) score += 5;
  if (staff.area && text.includes(staff.area.toLowerCase())) score += 3;
  if (text.includes("mri") && role.includes("imaging")) score += 4;
  if (text.includes("ct") && role.includes("imaging")) score += 4;
  if ((text.includes("theatre") || text.includes("surgery")) && (role.includes("surgeon") || role.includes("theatre"))) score += 4;
  if ((text.includes("ward") || text.includes("recovery")) && role.includes("nurse")) score += 4;
  if ((text.includes("consent") || text.includes("estimate") || text.includes("insurance") || text.includes("owner")) && (role.includes("admin") || role.includes("reception"))) score += 4;
  if (text.includes("pharmacy") && role.includes("pharmacy")) score += 4;
  return score;
}

function resourceScore(resource: ResourceOption, block: ScheduledWorkBlock) {
  const text = textFor(block);
  const resourceText = `${resource.name || ""} ${resource.type || ""}`.toLowerCase();
  let score = 0;
  if (block.where && resourceText.includes(block.where.toLowerCase())) score += 5;
  if (text.includes("mri") && resourceText.includes("mri")) score += 5;
  if (text.includes("ct") && resourceText.includes("ct")) score += 5;
  if ((text.includes("theatre") || text.includes("surgery")) && resourceText.includes("theatre")) score += 5;
  if ((text.includes("ward") || text.includes("recovery")) && (resourceText.includes("ward") || resourceText.includes("recovery"))) score += 4;
  if ((text.includes("consult") || text.includes("owner")) && (resourceText.includes("consult") || resourceText.includes("client"))) score += 3;
  return score;
}

export function QuickAssignActions({ block, onPatchBlock, onClearAssignment }: { block: ScheduledWorkBlock; onPatchBlock: PatchBlock; onClearAssignment: ClearBlock }) {
  const [staff, setStaff] = useState<StaffOption[]>([]);
  const [resources, setResources] = useState<ResourceOption[]>([]);

  useEffect(() => {
    fetch(`${API_BASE}/api/day-control/staff-options`).then((r) => r.json()).then((data) => setStaff(Array.isArray(data.staff) ? data.staff : [])).catch(() => setStaff([]));
    fetch(`${API_BASE}/api/day-control/resource-options`).then((r) => r.json()).then((data) => setResources(Array.isArray(data.resources) ? data.resources : [])).catch(() => setResources([]));
  }, []);

  const staffSuggestion = useMemo(() => staff.filter((item) => item.active !== false).map((item) => ({ item, score: roleScore(item, block) })).filter((entry) => entry.score > 0).sort((a, b) => b.score - a.score || a.item.name.localeCompare(b.item.name))[0]?.item, [staff, block]);
  const resourceSuggestion = useMemo(() => resources.filter((item) => item.active !== false).map((item) => ({ item, score: resourceScore(item, block) })).filter((entry) => entry.score > 0).sort((a, b) => b.score - a.score || a.item.name.localeCompare(b.item.name))[0]?.item, [resources, block]);

  function stop(event: React.MouseEvent) {
    event.stopPropagation();
  }

  function assignStaff(event: React.MouseEvent) {
    stop(event);
    if (!staffSuggestion) return;
    onPatchBlock(block.id, { assignedStaffId: staffSuggestion.id, assignedStaffName: staffSuggestion.name, assignedRole: staffSuggestion.role, status: "amber", next: "quick assigned staff" });
  }

  function assignResource(event: React.MouseEvent) {
    stop(event);
    if (!resourceSuggestion) return;
    onPatchBlock(block.id, { resourceId: resourceSuggestion.id, resourceName: resourceSuggestion.name, status: "amber", next: "quick assigned resource" });
  }

  function clear(event: React.MouseEvent) {
    stop(event);
    onClearAssignment(block.id);
  }

  return <span className="quickAssign" onClick={stop}><button type="button" disabled={!staffSuggestion} onClick={assignStaff}>{staffSuggestion ? `+ ${staffSuggestion.name}` : "+ staff"}</button><button type="button" disabled={!resourceSuggestion} onClick={assignResource}>{resourceSuggestion ? `+ ${resourceSuggestion.name}` : "+ resource"}</button><button type="button" onClick={clear}>clear</button></span>;
}

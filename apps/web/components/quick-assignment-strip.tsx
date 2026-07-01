"use client";

import { useEffect, useMemo, useState } from "react";
import type { ScheduledWorkBlock } from "@/lib/day-control-work";
import type { DayControlAssignmentPatch } from "@/lib/day-control-store";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

type StaffOption = { id: number; name: string; role: string; area: string; active?: boolean };
type ResourceOption = { id: string; name: string; type: string; active?: boolean };

type QuickAssignmentStripProps = {
  block: ScheduledWorkBlock;
  onAssign: (blockId: string, patch: DayControlAssignmentPatch) => void;
  onClear: (blockId: string) => void;
};

function text(block: ScheduledWorkBlock) {
  return `${block.assignedRole || ""} ${block.who || ""} ${block.what || ""} ${block.where || ""} ${block.how || ""}`.toLowerCase();
}

function matchesStaff(block: ScheduledWorkBlock, staff: StaffOption) {
  const haystack = text(block);
  const role = `${staff.role} ${staff.area}`.toLowerCase();
  if (!role.trim()) return true;
  return role.split(/\s+/).some((word) => word.length > 2 && haystack.includes(word));
}

function matchesResource(block: ScheduledWorkBlock, resource: ResourceOption) {
  const haystack = text(block);
  const source = `${resource.name} ${resource.type}`.toLowerCase();
  if (!source.trim()) return true;
  return source.split(/\s+/).some((word) => word.length > 2 && haystack.includes(word));
}

export function QuickAssignmentStrip({ block, onAssign, onClear }: QuickAssignmentStripProps) {
  const [staff, setStaff] = useState<StaffOption[]>([]);
  const [resources, setResources] = useState<ResourceOption[]>([]);
  const [staffId, setStaffId] = useState("");
  const [resourceId, setResourceId] = useState("");

  useEffect(() => {
    fetch(`${API_BASE}/api/day-control/staff-options`).then((r) => r.json()).then((data) => setStaff(Array.isArray(data.staff) ? data.staff : [])).catch(() => setStaff([]));
    fetch(`${API_BASE}/api/day-control/resource-options`).then((r) => r.json()).then((data) => setResources(Array.isArray(data.resources) ? data.resources : [])).catch(() => setResources([]));
  }, []);

  const staffOptions = useMemo(() => {
    const active = staff.filter((item) => item.active !== false);
    const suggested = active.filter((item) => matchesStaff(block, item));
    return [...suggested, ...active.filter((item) => !suggested.includes(item))].slice(0, 12);
  }, [block, staff]);

  const resourceOptions = useMemo(() => {
    const active = resources.filter((item) => item.active !== false);
    const suggested = active.filter((item) => matchesResource(block, item));
    return [...suggested, ...active.filter((item) => !suggested.includes(item))].slice(0, 12);
  }, [block, resources]);

  function assign() {
    const staffChoice = staffOptions.find((item) => String(item.id) === staffId);
    const resourceChoice = resourceOptions.find((item) => item.id === resourceId);
    onAssign(block.id, {
      assignedStaffId: staffChoice?.id,
      assignedStaffName: staffChoice?.name,
      assignedRole: staffChoice?.role || block.assignedRole || block.who,
      resourceId: resourceChoice?.id,
      resourceName: resourceChoice?.name || block.resourceName,
    });
  }

  return <section className="qas" onClick={(event) => event.stopPropagation()}><select value={staffId} onChange={(event) => setStaffId(event.target.value)}><option value="">Quick staff</option>{staffOptions.map((item) => <option key={item.id} value={item.id}>{item.name} — {item.role}</option>)}</select><select value={resourceId} onChange={(event) => setResourceId(event.target.value)}><option value="">Resource</option>{resourceOptions.map((item) => <option key={item.id} value={item.id}>{item.name} — {item.type}</option>)}</select><button type="button" onClick={assign}>Assign</button><button type="button" onClick={() => onClear(block.id)}>Clear</button></section>;
}

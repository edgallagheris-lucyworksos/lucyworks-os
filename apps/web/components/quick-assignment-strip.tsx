"use client";

import { useEffect, useMemo, useState, type MouseEvent } from "react";
import { procedureForWork } from "@/lib/clinical-catalogue";
import type { ScheduledWorkBlock } from "@/lib/day-control-work";
import type { DayControlAssignmentPatch } from "@/lib/day-control-store";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

type StaffOption = { id: number; name: string; role: string; area: string; active?: boolean };
type ResourceOption = { id: string; name: string; type: string; active?: boolean };
type ProtectedWindow = { start: number; end: number };
type Candidate<T> = { item: T; score: number; reasons: string[]; conflict?: { label: string; freeAfter: string } };

type QuickAssignmentStripProps = {
  block: ScheduledWorkBlock;
  blocks: ScheduledWorkBlock[];
  onAssign: (blockId: string, patch: DayControlAssignmentPatch) => void;
  onClear: (blockId: string) => void;
};

function safe(value: string | number | null | undefined) {
  return String(value || "").trim();
}

function text(block: ScheduledWorkBlock) {
  return `${safe(block.assignedRole)} ${safe(block.who)} ${safe(block.what)} ${safe(block.where)} ${safe(block.how)} ${safe(block.next)} ${safe(block.lane)}`.toLowerCase();
}

function minutes(time: string) {
  const [hour, minute] = time.split(":").map(Number);
  if (!Number.isFinite(hour) || !Number.isFinite(minute)) return 0;
  return hour * 60 + minute;
}

function hhmm(value: number) {
  const clamped = Math.max(0, value);
  return `${String(Math.floor(clamped / 60)).padStart(2, "0")}:${String(clamped % 60).padStart(2, "0")}`;
}

function protectedWindow(block: ScheduledWorkBlock): ProtectedWindow {
  const item = procedureForWork(`${block.what} ${block.how} ${block.where} ${block.next}`, block.lane);
  const visibleStart = minutes(block.time);
  const visibleMinutes = block.durationMinutes || item?.defaultMinutes || 15;
  const setup = item?.setupMinutes || 5;
  const handover = item?.handoverMinutes || 5;
  const contingency = item?.contingencyMinutes || 5;
  const admin = item?.referralAdminMinutes || 0;
  return { start: visibleStart - setup, end: visibleStart + visibleMinutes + handover + contingency + admin };
}

function overlaps(left: ProtectedWindow, right: ProtectedWindow) {
  return left.start < right.end && right.start < left.end;
}

function sameCase(left: ScheduledWorkBlock, right: ScheduledWorkBlock) {
  if (left.episodeRef && right.episodeRef) return left.episodeRef === right.episodeRef;
  if (left.subject && right.subject) return left.subject === right.subject;
  return false;
}

function staffMatchesBlock(candidate: StaffOption, block: ScheduledWorkBlock) {
  return block.assignedStaffId === candidate.id || safe(block.assignedStaffName).toLowerCase() === candidate.name.toLowerCase();
}

function resourceMatchesBlock(candidate: ResourceOption, block: ScheduledWorkBlock) {
  return block.resourceId === candidate.id || safe(block.resourceName || block.where).toLowerCase() === candidate.name.toLowerCase();
}

function conflictFor(block: ScheduledWorkBlock, blocks: ScheduledWorkBlock[], matches: (item: ScheduledWorkBlock) => boolean) {
  const targetWindow = protectedWindow(block);
  const clashes = blocks.filter((item) => item.id !== block.id && matches(item) && !sameCase(block, item) && overlaps(targetWindow, protectedWindow(item)));
  if (!clashes.length) return undefined;
  const latestEnd = Math.max(...clashes.map((item) => protectedWindow(item).end));
  return { label: clashes.map((item) => item.subject || item.what).join(" / "), freeAfter: hhmm(latestEnd) };
}

function staffScore(block: ScheduledWorkBlock, staff: StaffOption) {
  const haystack = text(block);
  const role = `${staff.role} ${staff.area}`.toLowerCase();
  const reasons: string[] = [];
  let score = 0;

  if (safe(block.assignedRole) && role.includes(safe(block.assignedRole).toLowerCase())) { score += 8; reasons.push("role match"); }
  if (safe(block.who) && role.includes(safe(block.who).toLowerCase())) { score += 6; reasons.push("owner role match"); }
  if (staff.area && haystack.includes(staff.area.toLowerCase())) { score += 4; reasons.push("area match"); }
  if (haystack.includes("mri") && role.includes("imaging")) { score += 6; reasons.push("imaging fit"); }
  if (haystack.includes("ct") && role.includes("imaging")) { score += 6; reasons.push("imaging fit"); }
  if ((haystack.includes("theatre") || haystack.includes("surgery") || haystack.includes("surgical")) && (role.includes("surgical") || role.includes("surgeon") || role.includes("theatre"))) { score += 6; reasons.push("theatre fit"); }
  if ((haystack.includes("anaesthesia") || haystack.includes("anaes") || haystack.includes("sedation") || haystack.includes("induction")) && role.includes("anaesthesia")) { score += 6; reasons.push("anaesthesia fit"); }
  if ((haystack.includes("ward") || haystack.includes("recovery") || haystack.includes("nursing")) && role.includes("nurse")) { score += 6; reasons.push("ward/recovery fit"); }
  if ((haystack.includes("consent") || haystack.includes("estimate") || haystack.includes("insurance") || haystack.includes("owner") || haystack.includes("client")) && (role.includes("admin") || role.includes("reception") || role.includes("client contact") || role.includes("insurance"))) { score += 6; reasons.push("admin/client fit"); }
  if (haystack.includes("pharmacy") && role.includes("pharmacy")) { score += 6; reasons.push("pharmacy fit"); }

  return { score, reasons };
}

function resourceScore(block: ScheduledWorkBlock, resource: ResourceOption) {
  const haystack = text(block);
  const source = `${resource.name} ${resource.type}`.toLowerCase();
  const reasons: string[] = [];
  let score = 0;

  if (safe(block.where) && source.includes(safe(block.where).toLowerCase())) { score += 8; reasons.push("location match"); }
  if (safe(block.resourceName) && source.includes(safe(block.resourceName).toLowerCase())) { score += 8; reasons.push("resource match"); }
  if (haystack.includes("mri") && source.includes("mri")) { score += 7; reasons.push("MRI fit"); }
  if (haystack.includes("ct") && source.includes("ct")) { score += 7; reasons.push("CT fit"); }
  if ((haystack.includes("theatre") || haystack.includes("surgery") || haystack.includes("surgical")) && source.includes("theatre")) { score += 7; reasons.push("theatre fit"); }
  if ((haystack.includes("ward") || haystack.includes("recovery")) && (source.includes("ward") || source.includes("recovery"))) { score += 6; reasons.push("ward/recovery fit"); }
  if ((haystack.includes("consult") || haystack.includes("owner") || haystack.includes("client")) && (source.includes("consult") || source.includes("client"))) { score += 4; reasons.push("client/consult fit"); }

  return { score, reasons };
}

function staffCandidates(block: ScheduledWorkBlock, blocks: ScheduledWorkBlock[], staff: StaffOption[]): Candidate<StaffOption>[] {
  return staff.filter((item) => item.active !== false).map((item) => {
    const scored = staffScore(block, item);
    return { item, score: scored.score, reasons: scored.reasons, conflict: conflictFor(block, blocks, (row) => staffMatchesBlock(item, row)) };
  }).filter((entry) => entry.score > 0 || !entry.conflict).sort((a, b) => Number(Boolean(a.conflict)) - Number(Boolean(b.conflict)) || b.score - a.score || a.item.name.localeCompare(b.item.name)).slice(0, 12);
}

function resourceCandidates(block: ScheduledWorkBlock, blocks: ScheduledWorkBlock[], resources: ResourceOption[]): Candidate<ResourceOption>[] {
  return resources.filter((item) => item.active !== false).map((item) => {
    const scored = resourceScore(block, item);
    return { item, score: scored.score, reasons: scored.reasons, conflict: conflictFor(block, blocks, (row) => resourceMatchesBlock(item, row)) };
  }).filter((entry) => entry.score > 0 || !entry.conflict).sort((a, b) => Number(Boolean(a.conflict)) - Number(Boolean(b.conflict)) || b.score - a.score || a.item.name.localeCompare(b.item.name)).slice(0, 12);
}

function staffLabel(candidate: Candidate<StaffOption>, recommended: boolean) {
  const warning = candidate.conflict ? ` busy until ${candidate.conflict.freeAfter}` : "";
  const prefix = recommended ? "recommended: " : "";
  return `${prefix}${candidate.item.name} - ${candidate.item.role}${warning}`;
}

function resourceLabel(candidate: Candidate<ResourceOption>, recommended: boolean) {
  const warning = candidate.conflict ? ` busy until ${candidate.conflict.freeAfter}` : "";
  const prefix = recommended ? "recommended: " : "";
  return `${prefix}${candidate.item.name} - ${candidate.item.type}${warning}`;
}

export function QuickAssignmentStrip({ block, blocks, onAssign, onClear }: QuickAssignmentStripProps) {
  const [staff, setStaff] = useState<StaffOption[]>([]);
  const [resources, setResources] = useState<ResourceOption[]>([]);
  const [staffId, setStaffId] = useState("");
  const [resourceId, setResourceId] = useState("");

  useEffect(() => {
    fetch(`${API_BASE}/api/day-control/staff-options`).then((r) => r.json()).then((data) => setStaff(Array.isArray(data.staff) ? data.staff : [])).catch(() => setStaff([]));
    fetch(`${API_BASE}/api/day-control/resource-options`).then((r) => r.json()).then((data) => setResources(Array.isArray(data.resources) ? data.resources : [])).catch(() => setResources([]));
  }, []);

  const staffOptions = useMemo(() => staffCandidates(block, blocks, staff), [block, blocks, staff]);
  const resourceOptions = useMemo(() => resourceCandidates(block, blocks, resources), [block, blocks, resources]);

  useEffect(() => {
    setStaffId(staffOptions[0] ? String(staffOptions[0].item.id) : "");
  }, [block.id, staffOptions]);

  useEffect(() => {
    setResourceId(resourceOptions[0]?.item.id || "");
  }, [block.id, resourceOptions]);

  const staffChoice = staffOptions.find((item) => String(item.item.id) === staffId);
  const resourceChoice = resourceOptions.find((item) => item.item.id === resourceId);
  const warnings = [staffChoice?.conflict ? `${staffChoice.item.name} busy until ${staffChoice.conflict.freeAfter}` : "", resourceChoice?.conflict ? `${resourceChoice.item.name} busy until ${resourceChoice.conflict.freeAfter}` : ""].filter(Boolean);
  const reason = [staffChoice?.reasons[0] ? `staff: ${staffChoice.reasons[0]}` : "", resourceChoice?.reasons[0] ? `resource: ${resourceChoice.reasons[0]}` : ""].filter(Boolean).join(" / ");

  function stop(event: MouseEvent) {
    event.stopPropagation();
  }

  function assign(event: MouseEvent) {
    stop(event);
    onAssign(block.id, {
      assignedStaffId: staffChoice?.item.id,
      assignedStaffName: staffChoice?.item.name,
      assignedRole: staffChoice?.item.role || block.assignedRole || block.who,
      resourceId: resourceChoice?.item.id,
      resourceName: resourceChoice?.item.name || block.resourceName,
    });
  }

  function clear(event: MouseEvent) {
    stop(event);
    onClear(block.id);
  }

  return <section className="qas" onClick={stop}><select value={staffId} onChange={(event) => setStaffId(event.target.value)} aria-label="Quick staff recommendation"><option value="">Quick staff</option>{staffOptions.map((candidate, index) => <option key={candidate.item.id} value={candidate.item.id}>{staffLabel(candidate, index === 0 && !candidate.conflict)}</option>)}</select><select value={resourceId} onChange={(event) => setResourceId(event.target.value)} aria-label="Resource recommendation"><option value="">Resource</option>{resourceOptions.map((candidate, index) => <option key={candidate.item.id} value={candidate.item.id}>{resourceLabel(candidate, index === 0 && !candidate.conflict)}</option>)}</select><button type="button" className={warnings.length ? "warn" : ""} onClick={assign}>{warnings.length ? "Assign with warning" : "Assign"}</button><button type="button" onClick={clear}>Clear</button><small className={warnings.length ? "qasWarn" : "qasReason"}>{warnings.length ? warnings.join(" / ") : reason || "recommended by role, area and protected time"}</small></section>;
}

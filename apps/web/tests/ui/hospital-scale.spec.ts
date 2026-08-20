import { expect, test, type Page } from "@playwright/test";

const base = new Date();
base.setHours(8, 0, 0, 0);
const iso = (minutes: number) => new Date(base.getTime() + minutes * 60_000).toISOString();

const areas = Array.from({ length: 40 }, (_, i) => ({
  areaRef: `room-${i + 1}`,
  name: i < 11 ? `Theatre ${i + 1}` : i < 16 ? `Imaging ${i - 10}` : i < 26 ? `Ward ${i - 15}` : `Consult ${i - 25}`,
  areaType: i < 11 ? "theatre" : i < 16 ? "imaging" : i < 26 ? "ward" : "consult",
  department: i < 11 ? "Surgery" : i < 16 ? "Diagnostic imaging" : i < 26 ? "Inpatient" : "Consulting",
  capacity: i < 26 ? 1 : 2,
  turnoverMinutes: i < 11 ? 20 : 10,
}));

const blocks = areas.slice(0, 32).map((area, i) => ({
  blockRef: `block-${i + 1}`,
  episodeRef: `EP-${1000 + i}`,
  patientRef: `P-${1000 + i}`,
  patientName: `Patient ${i + 1}`,
  procedureName: i < 11 ? "Procedure" : i < 16 ? "Diagnostic imaging" : "Clinical care",
  blockType: i < 11 ? "procedure" : "clinical",
  areaRef: area.areaRef,
  areaName: area.name,
  startsAt: iso((i % 8) * 30),
  endsAt: iso((i % 8) * 30 + 60),
  status: "planned",
  riskLevel: i === 3 ? "red" : "green",
  priority: 50,
  leadStaffRef: `staff-${i + 1}`,
  leadStaffName: `Staff ${i + 1}`,
  leadStaffRole: "clinician",
  assistantRefs: [], equipmentRefs: [], requiredSkills: [], blockers: i === 3 ? [{ code: "capacity" }] : [], gates: {}, version: 1,
}));

const staffBlocks = Array.from({ length: 100 }, (_, i) => ({
  id: `work-${i + 1}`,
  time: "08:00",
  lane: "clinical",
  subject: `Patient ${i + 1}`,
  what: "Hospital work",
  who: i % 3 === 0 ? "nurse" : "clinician",
  assignedRole: i % 3 === 0 ? "nurse" : "clinician",
  assignedStaffId: i + 1,
  assignedStaffName: `Staff ${i + 1}`,
  where: areas[i % areas.length].name,
  how: "standard workflow",
  next: "continue planned flow",
  blocker: i === 3 ? "capacity conflict" : "none",
  status: i === 3 ? "red" : "green",
  route: "/workspace",
}));

const hospitalBoard = {
  generatedAt: iso(0), operationalDate: iso(0).slice(0, 10), boardVersion: "11.0",
  premises: { premisesRef: "hospital-main", name: "Bristol Referral Hospital" },
  areas, blocks,
  episodes: blocks.map(block => ({ episodeRef: block.episodeRef, patientRef: block.patientRef, patientName: block.patientName, phase: "active", urgency: "routine", ownerRole: "clinician", currentAreaRef: block.areaRef, nextAction: block.procedureName, status: "active", version: 1 })),
  conflicts: [{ conflictRef: "conflict-1", conflictType: "capacity", severity: "red", primaryBlockRef: "block-4", relatedRefs: [], explanation: "Capacity conflict", options: [] }],
  summary: { blocks: blocks.length, episodes: blocks.length, redConflicts: 1, amberConflicts: 0, unassignedBlocks: 0, blockedBlocks: 1, lastChangeId: 1 },
  liveWindow: { from: iso(0), to: iso(90), blocks: blocks.slice(0, 8) },
};

async function mock(page: Page) {
  await page.route("**/api/**", async route => {
    const path = new URL(route.request().url()).pathname.replace(/^\/_lucyworks_api/, "");
    if (path === "/api/auth/me") return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ user: { id: "scale-test", subject: "scale-test", name: "Ops Lead", role: "ops_manager", verified: true } }) });
    if (path === "/api/v26/context") return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ context: { organisationRef: "bvs", siteRef: "hospital-main", premisesRef: "hospital-main", version: 1 }, sites: [{ organisationRef: "bvs", siteRef: "hospital-main", premisesRef: "hospital-main", name: "Bristol Referral Hospital", role: "ops_manager" }] }) });
    if (path === "/api/v26/operational-view") return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ summary: { activeImpacts: 1, openCommands: 0, affectedPatients: 1, severityCounts: { red: 1 } } }) });
    if (path === "/api/v11/master-board/day") return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(hospitalBoard) });
    if (path === "/api/day-control/blocks") return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ blocks: staffBlocks }) });
    return route.fulfill({ status: 200, contentType: "application/json", body: "{}" });
  });
}

test.beforeEach(async ({ page }) => { await mock(page); });

test("command centre handles forty rooms and one hundred staff without turning them into cards", async ({ page }) => {
  await page.goto("/hospital-board", { waitUntil: "networkidle" });
  await expect(page.locator(".roomRow")).toHaveCount(40);
  await expect(page.locator(".staffList button")).toHaveCount(100);
  await expect(page.getByText("40 rooms / areas")).toBeVisible();
  await expect(page.getByText(/100 staff represented/)).toBeVisible();
});

test("room, staff, exception and case controls all change real state", async ({ page }) => {
  await page.goto("/hospital-board", { waitUntil: "networkidle" });
  await page.getByLabel("Search hospital command").fill("Theatre 1");
  await expect(page.locator(".roomRow")).toHaveCount(1);
  await page.getByLabel("Search hospital command").fill("");
  await page.getByRole("button", { name: "Exceptions only" }).click();
  await expect(page.getByRole("button", { name: "Showing exceptions" })).toBeVisible();
  await page.getByRole("button", { name: "Showing exceptions" }).click();
  await page.getByLabel("Search staff").fill("Staff 77");
  await expect(page.locator(".staffList button")).toHaveCount(1);
  await page.locator(".staffList button").first().click();
  await expect(page.getByLabel("Search hospital command")).toHaveValue("Staff 77");
  await page.getByLabel("Search hospital command").fill("");
  await page.locator(".caseBlock").first().click();
  await expect(page.getByRole("link", { name: "Patient record" })).toHaveAttribute("href", "/patient-record?episode=EP-1000");
  await expect(page.getByRole("link", { name: "Patient work" })).toHaveAttribute("href", "/clinical-execution?episode=EP-1000");
  await page.getByRole("button", { name: "Close selected case" }).click();
  await expect(page.getByLabel("Selected case")).toHaveCount(0);
});

test("the detailed scheduler and staffing views remain reachable from the same hospital page", async ({ page }) => {
  await page.goto("/hospital-board", { waitUntil: "networkidle" });
  await page.getByRole("button", { name: "Schedule control" }).click();
  await expect(page.getByRole("heading", { name: "15-minute operating grid" })).toBeVisible();
  await page.getByRole("button", { name: "Staff detail" }).click();
  await expect(page.locator(".slg")).toBeVisible();
  await page.getByRole("button", { name: "Command centre" }).click();
  await expect(page.locator(".hccRooms")).toBeVisible();
});

import { expect, test, type Page } from "@playwright/test";

const now = new Date().toISOString();
const later = new Date(Date.now() + 60 * 60_000).toISOString();

const hospitalBoard = {
  generatedAt: now,
  operationalDate: now.slice(0, 10),
  areas: [
    { areaRef: "theatre-1", areaType: "theatre", capacity: 1 },
    { areaRef: "mri-1", areaType: "imaging", capacity: 1 },
  ],
  blocks: [
    { blockRef: "block-1", episodeRef: "EP-1001", patientName: "Mabel", procedureName: "MRI spine", areaRef: "mri-1", areaName: "MRI", startsAt: now, endsAt: later, status: "planned", riskLevel: "green", leadStaffName: "A. Nurse" },
    { blockRef: "block-2", episodeRef: "EP-1002", patientName: "Oscar", procedureName: "Surgical review", areaRef: "theatre-1", areaName: "Theatre 1", startsAt: later, endsAt: new Date(Date.now() + 2 * 60 * 60_000).toISOString(), status: "planned", riskLevel: "amber", leadStaffName: "Dr Patel" },
  ],
  episodes: [
    { episodeRef: "EP-1001", patientName: "Mabel", phase: "diagnostics", urgency: "urgent", ownerRole: "clinician", nextAction: "MRI spine", status: "active" },
    { episodeRef: "EP-1002", patientName: "Oscar", phase: "pre_op", urgency: "routine", ownerRole: "nurse", nextAction: "Prepare for theatre", status: "active" },
    { episodeRef: "EP-1003", patientName: "Luna", phase: "referral_received", urgency: "urgent", ownerRole: "reception", nextAction: "Clinical triage", status: "active" },
  ],
  conflicts: [],
  summary: { blocks: 2, episodes: 3, redConflicts: 0, amberConflicts: 0, unassignedBlocks: 0, blockedBlocks: 0 },
  liveWindow: { blocks: [{ blockRef: "block-1", episodeRef: "EP-1001", patientName: "Mabel", procedureName: "MRI spine", areaRef: "mri-1", areaName: "MRI", startsAt: now, endsAt: later, status: "planned", riskLevel: "green", leadStaffName: "A. Nurse" }] },
};

const workspace = {
  generatedAt: now,
  summary: { activePatients: 3, scheduledPatients: 2, unscheduledPatients: 1, unlinkedTasks: 0 },
  patientFlow: [
    { episodeRef: "EP-1001", patientName: "Mabel", urgency: "urgent", phase: "diagnostics", ownerRole: "clinician", currentAreaRef: "mri-1", currentAreaName: "MRI", nextAction: "MRI spine", scheduled: true, attention: [], taskCount: 1, redTaskCount: 0, overdueTaskCount: 0, schedule: [hospitalBoard.blocks[0]] },
    { episodeRef: "EP-1003", patientName: "Luna", urgency: "urgent", phase: "referral_received", ownerRole: "reception", currentAreaRef: null, currentAreaName: null, nextAction: "Clinical triage", scheduled: false, attention: ["Triage owner required"], taskCount: 1, redTaskCount: 0, overdueTaskCount: 0, schedule: [] },
  ],
  tasks: [{ id: 1, title: "Clinical triage", description: "Review referral and assign clinical owner", urgency: "urgent", status: "new", ownerRole: "clinician", patientName: "Luna", episodeRef: "EP-1003", sectionName: "Referral", roomName: null, dueAt: later, overdue: false }],
  unlinkedTasks: [],
  conflicts: [],
};

async function mockHospitalApi(page: Page) {
  await page.route("**/api/**", async route => {
    const url = new URL(route.request().url());
    if (url.pathname === "/api/auth/me") {
      return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ user: { id: "ui-test", subject: "ui-test", name: "Alex Morgan", role: "ops_manager", verified: true } }) });
    }
    if (url.pathname === "/api/v11/master-board/day") {
      return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(hospitalBoard) });
    }
    if (url.pathname === "/api/v14/operational-workspace") {
      return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(workspace) });
    }
    if (["/api/v9/referrals", "/api/v12/identity-intakes", "/api/v12/triage"].includes(url.pathname)) {
      return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ items: [] }) });
    }
    return route.fulfill({ status: 200, contentType: "application/json", body: "{}" });
  });
}

async function assertProfessionalSurface(page: Page, path: string, expectedHeading: RegExp, screenshotName: string) {
  await page.goto(path, { waitUntil: "networkidle" });
  await expect(page.getByRole("heading", { name: expectedHeading }).first()).toBeVisible();
  const bodyText = (await page.locator("body").innerText()).toLowerCase();
  for (const forbidden of ["prototype", "synthetic referral", "patient command v16", "guided referral intake v31", "automation v23"]) {
    expect(bodyText).not.toContain(forbidden);
  }
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow).toBeLessThanOrEqual(2);
  await page.screenshot({ path: `test-results/screenshots/${screenshotName}.png`, fullPage: true });
}

for (const viewport of [
  { name: "desktop", width: 1440, height: 1000 },
  { name: "tablet", width: 900, height: 1100 },
  { name: "phone", width: 390, height: 844 },
]) {
  test.describe(viewport.name, () => {
    test.use({ viewport: { width: viewport.width, height: viewport.height } });

    test.beforeEach(async ({ page }) => {
      await mockHospitalApi(page);
      await page.addInitScript(() => {
        window.localStorage.setItem("lucyworks.premisesRef", "hospital-main");
        window.localStorage.setItem("lucyworks.siteName", "Bristol Referral Hospital");
      });
    });

    test("hospital operations renders without prototype artefacts or overflow", async ({ page }) => {
      await assertProfessionalSurface(page, "/hospital-board", /Hospital operations/i, `hospital-${viewport.name}`);
      await expect(page.getByText("Mabel").first()).toBeVisible();
      await expect(page.getByText("Bristol Referral Hospital").first()).toBeVisible();
    });

    test("referral intake renders as a staff workflow", async ({ page }) => {
      await assertProfessionalSurface(page, "/referral-intake", /Referral intake/i, `referral-${viewport.name}`);
      await expect(page.getByText("Owner & authority")).toBeVisible();
    });

    test("patient workspace renders care-first", async ({ page }) => {
      await assertProfessionalSurface(page, "/workspace", /Patient workspace/i, `workspace-${viewport.name}`);
      await expect(page.getByText("Mabel").first()).toBeVisible();
      await expect(page.getByText("Critical attention")).toBeVisible();
    });
  });
}

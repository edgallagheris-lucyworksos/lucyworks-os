import { expect, test, type Page } from "@playwright/test";

const now = new Date().toISOString();
const later = new Date(Date.now() + 60 * 60_000).toISOString();

const hospitalBoard = {
  generatedAt: now,
  operationalDate: now.slice(0, 10),
  boardVersion: "11.0",
  premises: { premisesRef: "bvs-bristol", name: "Bristol Referral Hospital" },
  areas: [
    { areaRef: "theatre-1", name: "Theatre 1", areaType: "theatre", department: "Surgery", capacity: 1, turnoverMinutes: 20 },
    { areaRef: "mri-1", name: "MRI", areaType: "imaging", department: "Diagnostic imaging", capacity: 1, turnoverMinutes: 15 },
  ],
  blocks: [
    { blockRef: "block-1", episodeRef: "EP-1001", patientRef: "P-1001", patientName: "Mabel", procedureName: "MRI spine", blockType: "diagnostic", areaRef: "mri-1", areaName: "MRI", startsAt: now, endsAt: later, status: "planned", riskLevel: "green", priority: 50, leadStaffRef: "staff-1", leadStaffName: "A. Nurse", leadStaffRole: "nurse", assistantRefs: [], equipmentRefs: [], requiredSkills: [], blockers: [], gates: {}, version: 1 },
    { blockRef: "block-2", episodeRef: "EP-1002", patientRef: "P-1002", patientName: "Oscar", procedureName: "Surgical review", blockType: "procedure", areaRef: "theatre-1", areaName: "Theatre 1", startsAt: later, endsAt: new Date(Date.now() + 2 * 60 * 60_000).toISOString(), status: "planned", riskLevel: "amber", priority: 40, leadStaffRef: "staff-2", leadStaffName: "Dr Patel", leadStaffRole: "clinician", assistantRefs: [], equipmentRefs: [], requiredSkills: ["surgical"], blockers: [], gates: {}, version: 1 },
  ],
  episodes: [
    { episodeRef: "EP-1001", patientRef: "P-1001", patientName: "Mabel", phase: "diagnostics", urgency: "urgent", ownerRole: "clinician", currentAreaRef: "mri-1", nextAction: "MRI spine", status: "active", version: 1 },
    { episodeRef: "EP-1002", patientRef: "P-1002", patientName: "Oscar", phase: "pre_op", urgency: "routine", ownerRole: "nurse", currentAreaRef: "theatre-1", nextAction: "Prepare for theatre", status: "active", version: 1 },
    { episodeRef: "EP-1003", patientRef: "P-1003", patientName: "Luna", phase: "referral_received", urgency: "urgent", ownerRole: "reception", nextAction: "Clinical triage", status: "active", version: 1 },
  ],
  conflicts: [],
  summary: { blocks: 2, episodes: 3, redConflicts: 0, amberConflicts: 0, unassignedBlocks: 0, blockedBlocks: 0, lastChangeId: 1 },
  liveWindow: { from: now, to: later, blocks: [] },
};

const patientCoordination = {
  generatedAt: now,
  handovers: [
    { id: 21, handoverRef: "handover-21", episodeRef: "EP-1001", fromActor: "Dr Patel", fromRole: "clinician", toActor: "A. Nurse", toRole: "nurse", status: "pending", summary: "Monitor after MRI", clinicalRisks: ["post-sedation airway risk"], outstandingActions: ["repeat observations"], dueAt: later },
  ],
  criticalResults: [
    { id: 31, resultRef: "result-31", episodeRef: "EP-1001", resultType: "potassium", severity: "red", summary: "Critical potassium", status: "awaiting_acknowledgement", assignedTo: "Dr Patel", assignedRole: "clinician", dueAt: later },
  ],
  diagnostics: [
    { workRef: "diagnostic-31", episodeRef: "EP-1001", modality: "laboratory", requestedTest: "potassium", urgency: "urgent", status: "reported", assignedService: "laboratory", reportSummary: "Critical potassium", criticalResult: true, version: 2 },
  ],
  tasks: [
    { taskRef: "task-31", episodeRef: "EP-1001", title: "Repeat observations", status: "due", dueAt: now, priority: "red", assignedRole: "nurse", version: 1 },
  ],
  observations: [
    { observationRef: "observation-31", episodeRef: "EP-1001", type: "respiratory_rate", concernLevel: "red", escalationStatus: "pending", recordedAt: now },
  ],
  summary: { pendingHandovers: 1, unacknowledgedCriticalResults: 1, overdueTasks: 1, redObservations: 1 },
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

const careBrief = {
  generatedAt: now,
  episodeRef: "EP-1001",
  patientName: "Mabel",
  patientRef: "P-1001",
  status: "active",
  urgency: "urgent",
  phase: "diagnostics",
  serviceLine: "neurology",
  recordedControlsReady: true,
  who: { accountableRole: "clinician", leadName: "Dr Patel", leadRole: "clinician" },
  what: { currentPhase: "diagnostics", currentOrNextProcedure: "MRI spine", nextAction: "Complete MRI and review findings" },
  where: { areaRef: "mri-1", areaName: "MRI" },
  when: { startsAt: now, endsAt: later, nextDeadline: null },
  how: { gateGaps: [], blockers: [], openTaskCount: 1, criticalTaskCount: 0, openConflictCount: 0, attention: [] },
  why: { urgency: "urgent", flags: [], conflicts: [] },
  schedule: [{ blockRef: "block-1", procedureName: "MRI spine", areaName: "MRI", startsAt: now, endsAt: later, status: "planned", riskLevel: "green", leadStaffName: "A. Nurse" }],
  tasks: [{ id: 7, title: "Review MRI findings", description: "Review images and confirm next clinical action", urgency: "urgent", status: "new", ownerRole: "clinician", area: "MRI", dueAt: later, overdue: false }],
  links: { patientCommand: "/workspace", hospitalBoard: "/hospital-board", episodeCommand: "/episode-command?episode=EP-1001", patientRecord: "/patient-record?episode=EP-1001", clinicalExecution: "/clinical-execution?episode=EP-1001" },
  clinicalBoundary: "Clinical decisions remain with the responsible clinician.",
};

const workforceDashboard = {
  workforce: [
    { staffRef: "staff-1", displayName: "A. Nurse", employmentStatus: "active", primaryRoleRef: "nurse", departmentRef: "diagnostic_imaging", gradeOrTrainingLevel: "senior", onCallEligible: true, sourceStatus: "verified" },
    { staffRef: "staff-2", displayName: "Dr Patel", employmentStatus: "active", primaryRoleRef: "clinician", departmentRef: "surgery", gradeOrTrainingLevel: "specialist", onCallEligible: true, sourceStatus: "verified" },
  ],
  competencies: [
    { staffRef: "staff-1", competencyRef: "mri_safety", scopeRef: "mri-1", level: "independent", status: "verified", validUntil: null },
    { staffRef: "staff-2", competencyRef: "surgical", scopeRef: "theatre-1", level: "independent", status: "verified", validUntil: null },
  ],
  summary: { workforceProfiles: 2, provisionalCompetencies: 0 },
};

const workforceRoster = {
  shifts: [
    { shiftRef: "shift-1", staffRef: "staff-1", departmentRef: "diagnostic_imaging", areaRef: "mri-1", startsAt: now, endsAt: later, shiftType: "standard", status: "active", onCall: false, sourceStatus: "verified" },
  ],
  availabilityExceptions: [],
};

const workforceAssessment = {
  assessedAt: now,
  activeShiftCount: 1,
  approvedExceptionCount: 0,
  gapCount: 0,
  safeToOperate: true,
  requirements: [
    { requirement: { requirementRef: "coverage-mri", serviceRef: "diagnostic_imaging", areaRef: "mri-1", roleRef: "nurse", competencyRef: "mri_safety", minimumCount: 1 }, eligibleStaffRefs: ["staff-1"], eligibleCount: 1, excluded: [], gap: 0, status: "met" },
  ],
  staffRisks: {},
  unprofiledShifts: [],
};

async function mockHospitalApi(page: Page) {
  await page.route("**/api/**", async route => {
    const url = new URL(route.request().url());
    const pathname = url.pathname.replace(/^\/_lucyworks_api/, "");
    if (pathname === "/api/auth/me") {
      return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ user: { id: "ui-test", subject: "ui-test", name: "Alex Morgan", role: "ops_manager", verified: true } }) });
    }
    if (pathname === "/api/v26/context") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          context: { organisationRef: "bvs", siteRef: "bvs-bristol", premisesRef: "bvs-bristol", version: 1 },
          sites: [{ organisationRef: "bvs", siteRef: "bvs-bristol", premisesRef: "bvs-bristol", name: "Bristol Referral Hospital", role: "ops_manager", isPrimary: true }],
        }),
      });
    }
    if (pathname === "/api/v11/master-board/day") {
      return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(hospitalBoard) });
    }
    if (pathname === "/api/v11/master-board/coordination") {
      return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(patientCoordination) });
    }
    if (pathname === "/api/bvs-v6/dashboard") {
      return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(workforceDashboard) });
    }
    if (pathname === "/api/bvs-v6/rota") {
      return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(workforceRoster) });
    }
    if (pathname === "/api/bvs-v6/rota/assessment") {
      return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(workforceAssessment) });
    }
    if (pathname === "/api/v9/episodes/EP-1001/command-view") {
      return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ episode: hospitalBoard.episodes[0], nextTransitions: {} }) });
    }
    if (pathname === "/api/v14/operational-workspace") {
      return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(workspace) });
    }
    if (pathname === "/api/v16/care-brief/EP-1001") {
      return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(careBrief) });
    }
    if (["/api/v9/referrals", "/api/v12/identity-intakes", "/api/v12/triage"].includes(pathname)) {
      return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ items: [] }) });
    }
    return route.fulfill({ status: 200, contentType: "application/json", body: "{}" });
  });
}

async function assertProfessionalSurface(page: Page, path: string, expectedHeading: RegExp, screenshotName: string) {
  await page.goto(path, { waitUntil: "networkidle" });
  await expect(page.getByRole("heading", { name: expectedHeading }).first()).toBeVisible();
  const bodyText = (await page.locator("body").innerText()).toLowerCase();
  for (const forbidden of ["prototype", "synthetic referral", "patient command v16", "guided referral intake v31", "care brief v16", "automation v23"]) {
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
    });

    test("hospital operations renders without prototype artefacts or overflow", async ({ page }) => {
      await assertProfessionalSurface(page, "/hospital-board", /Hospital operations/i, `hospital-${viewport.name}`);
      await expect(page.getByRole("heading", { name: "Today’s operating position" })).toBeVisible();
      await expect(page.getByText("Source: authenticated v11 hospital master board")).toBeVisible();
      await page.getByRole("button", { name: "Patient flow" }).first().click();
      await expect(page.getByRole("heading", { name: "Active patients" })).toBeVisible();
      await expect(page.getByRole("link", { name: /Mabel/i })).toBeVisible();
      await expect(page.getByText("Source: authenticated v11 master board and coordination projection")).toBeVisible();
      await page.getByRole("button", { name: "Manage" }).first().click();
      await expect(page.getByRole("dialog").getByRole("heading", { name: "Mabel" })).toBeVisible();
      await expect(page.getByRole("heading", { name: "Create accountable handover" })).toBeVisible();
      await expect(page.getByText("Critical potassium").first()).toBeVisible();
      await page.getByRole("button", { name: "Close patient coordination" }).click();
      await page.getByRole("button", { name: "Workforce" }).click();
      await expect(page.getByRole("heading", { name: "Workforce and safe coverage" })).toBeVisible();
      await expect(page.getByText("Source: authenticated workforce, rota and coverage services")).toBeVisible();
      await page.getByRole("button", { name: "Resource grid" }).first().click();
      await expect(page.getByRole("heading", { name: "15-minute operating grid" })).toBeVisible();
      await expect(page.locator(".hospital-shell__identity").getByText("Bristol Referral Hospital", { exact: true })).toBeVisible();
      await page.locator('[data-block-ref="block-1"]').click();
      await expect(page.getByRole("heading", { name: "Recorded gates" })).toBeVisible();
      await expect(page.getByRole("button", { name: "−15 min" })).toBeVisible();
      await expect(page.getByRole("button", { name: "Save assignment" })).toBeVisible();
      await expect(page.getByRole("button", { name: "Preview consequences" })).toBeVisible();
    });

    test("referral intake renders as a staff workflow", async ({ page }) => {
      await assertProfessionalSurface(page, "/referral-intake", /Referral intake/i, `referral-${viewport.name}`);
      await page.locator(".ri-steps button").nth(1).click();
      await expect(page.getByRole("heading", { name: "Owner & authority" })).toBeVisible();
    });

    test("patient workspace renders care-first", async ({ page }) => {
      await assertProfessionalSurface(page, "/workspace", /Patient workspace/i, `workspace-${viewport.name}`);
      await expect(page.getByText("Mabel").first()).toBeVisible();
      await expect(page.getByText("Critical attention")).toBeVisible();
    });

    test("care brief stays consistent with the professional shell", async ({ page }) => {
      await assertProfessionalSurface(page, "/care?episode=EP-1001", /Care brief/i, `care-${viewport.name}`);
      await expect(page.getByRole("heading", { name: "Mabel" })).toBeVisible();
      await expect(page.getByText("Controls clear")).toBeVisible();
    });
  });
}

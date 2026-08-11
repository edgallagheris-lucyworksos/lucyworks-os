import { expect, test, type Page } from "@playwright/test";

async function mockApi(page: Page) {
  await page.route("**/api/**", async route => {
    const url = new URL(route.request().url());
    if (url.pathname === "/api/auth/me") {
      return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ user: { id: "clinical-ui", subject: "clinical-ui", name: "Alex Morgan", role: "clinician", verified: true } }) });
    }
    if (url.pathname === "/api/clinical-execution/governed/dashboard") {
      return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({
        summary: { dueAdministrations: 1, activeAnaesthesia: 0, redObservations: 0, openTasks: 2, pendingDiagnostics: 1 },
        medicationOrders: [], administrations: [], anaesthesia: [], observations: [], tasks: [], diagnostics: [], dischargePlans: [], inventory: [], inventoryMovements: [], controlledDrugEntries: [],
      }) });
    }
    return route.fulfill({ status: 200, contentType: "application/json", body: "{}" });
  });
}

async function check(page: Page, path: string, heading: RegExp) {
  await page.goto(path, { waitUntil: "networkidle" });
  await expect(page.getByRole("heading", { name: heading }).first()).toBeVisible();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow).toBeLessThanOrEqual(2);
  const body = (await page.locator("body").innerText()).toLowerCase();
  expect(body).not.toContain("care brief v16");
  expect(body).not.toContain("patient command v16");
  expect(body).not.toContain("automation v23");
  expect(body).not.toContain("demo hospital");
}

for (const viewport of [
  { name: "desktop", width: 1440, height: 1000 },
  { name: "tablet", width: 900, height: 1100 },
  { name: "phone", width: 390, height: 844 },
]) {
  test.describe(`deep clinical ${viewport.name}`, () => {
    test.use({ viewport: { width: viewport.width, height: viewport.height } });
    test.beforeEach(async ({ page }) => {
      await mockApi(page);
      await page.addInitScript(() => {
        window.localStorage.setItem("lucyworks_session_user", JSON.stringify({ user: { id: "clinical-ui", name: "Alex Morgan", role: "clinician", verified: true }, expiresAt: null }));
      });
    });

    test("patient record uses the professional route shell", async ({ page }) => {
      await check(page, "/patient-record", /Patient record/i);
      const header = page.locator(".patient-record-surface main > header").first();
      await expect(header).toBeVisible();
      await expect(header).toHaveCSS("color", "rgb(15, 23, 42)");
      await page.screenshot({ path: `test-results/screenshots/patient-record-${viewport.name}.png`, fullPage: true });
    });

    test("patient work uses the professional route shell", async ({ page }) => {
      await check(page, "/clinical-execution", /Patient work/i);
      const header = page.locator(".clinical-work-surface main > header").first();
      await expect(header).toBeVisible();
      await expect(header).toHaveCSS("color", "rgb(15, 23, 42)");
      await page.screenshot({ path: `test-results/screenshots/patient-work-${viewport.name}.png`, fullPage: true });
    });

    test("operations directory remains restrained", async ({ page }) => {
      await check(page, "/system-control", /Operations directory/i);
      await page.screenshot({ path: `test-results/screenshots/system-control-${viewport.name}.png`, fullPage: true });
    });
  });
}

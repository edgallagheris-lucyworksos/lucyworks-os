import { expect, test, type Page } from "@playwright/test";

const user = { id: "functional-test", subject: "functional-test", name: "Alex Morgan", role: "ops_manager", verified: true };
const context = {
  context: { contextRef: "ctx-1", organisationRef: "bvs", siteRef: "bvs-bristol", premisesRef: "bvs-bristol", version: 2 },
  sites: [
    { organisationRef: "bvs", siteRef: "bvs-bristol", premisesRef: "bvs-bristol", name: "Bristol Referral Hospital", configurationState: "active", role: "ops_manager" },
    { organisationRef: "bvs", siteRef: "bvs-north", premisesRef: "bvs-north", name: "North Referral Hospital", configurationState: "active", role: "ops_manager" },
  ],
};

async function mockFunctionalApi(page: Page) {
  let contextReads = 0;
  await page.route("**/api/**", async route => {
    const url = new URL(route.request().url());
    const pathname = url.pathname.replace(/^\/_lucyworks_api/, "");
    if (pathname === "/api/auth/me") return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ user }) });
    if (pathname === "/api/v26/context") {
      contextReads += 1;
      return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(context) });
    }
    if (pathname === "/api/v26/operational-view") {
      return route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ detail: "impact feed temporarily unavailable" }) });
    }
    if (pathname === "/api/v26/context/switch" && route.request().method() === "POST") {
      return route.fulfill({ status: 409, contentType: "application/json", body: JSON.stringify({ code: "database_integrity_conflict", message: "The stable reference or idempotency key already exists. Refresh the current record instead of repeating the write." }) });
    }
    if (pathname === "/api/alerts") return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ total_alerts: 0, high_alerts: 0 }) });
    if (pathname === "/api/input/capture" && route.request().method() === "POST") {
      return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ ok: true, work_item: { id: 91, title: "MRI owner update overdue" } }) });
    }
    return route.fulfill({ status: 200, contentType: "application/json", body: "{}" });
  });
  return () => contextReads;
}

const shellLinks = [
  ["Patients", "/workspace"],
  ["Hospital today", "/hospital-board"],
  ["Referrals", "/referral-intake"],
  ["Quick input", "/input"],
  ["My work", "/my-shift"],
] as const;

const moreLinks = [
  ["Patient work", "/clinical-execution"],
  ["Patient record", "/patient-record"],
  ["Resources", "/resources"],
  ["Rota", "/workforce-rota"],
  ["Safety control", "/control-plane"],
  ["System tools", "/system-control"],
] as const;

test.beforeEach(async ({ page }) => {
  await mockFunctionalApi(page);
});

test("every hospital-shell navigation control has a real route target", async ({ page }) => {
  await page.goto("/input", { waitUntil: "networkidle" });
  for (const [label, path] of shellLinks) {
    const link = page.getByRole("link", { name: label, exact: true }).first();
    await expect(link).toHaveAttribute("href", path);
  }
  await page.getByText("More tools", { exact: true }).click();
  for (const [label, path] of moreLinks) {
    const link = page.getByRole("link", { name: label, exact: true }).first();
    await expect(link).toHaveAttribute("href", path);
  }
});

test("primary navigation actually changes route and returns", async ({ page }) => {
  await page.goto("/input", { waitUntil: "networkidle" });
  await page.getByRole("link", { name: "Patients", exact: true }).first().click();
  await expect(page).toHaveURL(/\/workspace(?:\?|$)/);
  await page.getByRole("link", { name: "Quick input", exact: true }).first().click();
  await expect(page).toHaveURL(/\/input(?:\?|$)/);
  await page.getByRole("link", { name: "Referrals", exact: true }).first().click();
  await expect(page).toHaveURL(/\/referral-intake(?:\?|$)/);
});

test("quick input creates owned work instead of being a decorative control", async ({ page }) => {
  await page.goto("/input", { waitUntil: "networkidle" });
  await page.getByLabel("What needs attention").fill("MRI owner update overdue");
  await page.getByRole("button", { name: "Create owned work" }).click();
  await expect(page.getByText(/Work item #91 created/)).toBeVisible();
});

test("optional impact-feed failure does not make hospital identity unavailable", async ({ page }) => {
  await page.goto("/input", { waitUntil: "networkidle" });
  await expect(page.getByText("ACTIVE HOSPITAL", { exact: true })).toBeVisible();
  await expect(page.getByText("Live impact summary unavailable", { exact: true })).toBeVisible();
  await expect(page.getByText(/Hospital context unavailable/i)).toHaveCount(0);
});

test("duplicate context write recovers by refreshing current context", async ({ page }) => {
  const reads = await mockFunctionalApi(page);
  await page.goto("/input", { waitUntil: "networkidle" });
  await page.getByLabel("Select authorised hospital site").selectOption("bvs-north");
  await expect(page.getByRole("status")).toContainText("already been recorded");
  expect(reads()).toBeGreaterThan(1);
  await expect(page.getByText(/database_integrity_conflict/i)).toHaveCount(0);
});

test("speech blocker has a resolvable identity-and-authority path", async ({ page }) => {
  await page.goto("/input", { waitUntil: "networkidle" });
  const setup = page.getByRole("link", { name: /Confirm identity.*recording authority/i }).first();
  await expect(setup).toBeVisible();
  await setup.click();
  await expect(page).toHaveURL(/\/speech-authority\?returnTo=%2Finput|\/speech-authority\?returnTo=\/input/);
  await expect(page.getByRole("heading", { name: /Confirm identity.*recording authority/i })).toBeVisible();
  await expect(page.getByText("Alex Morgan", { exact: true })).toBeVisible();
  await expect(page.getByText("Bristol Referral Hospital", { exact: true })).toBeVisible();
  await page.getByRole("checkbox").check();
  await page.getByRole("button", { name: "Confirm and continue" }).click();
  await expect(page.getByRole("link", { name: /Return to speech capture/i })).toBeVisible();
  await page.getByRole("link", { name: /Return to speech capture/i }).click();
  await expect(page).toHaveURL(/\/input(?:\?|$)/);
});

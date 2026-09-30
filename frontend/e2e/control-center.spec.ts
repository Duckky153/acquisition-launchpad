import AxeBuilder from "@axe-core/playwright";
import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

const apiBase = process.env.LAUNCHPAD_E2E_API_BASE_URL ?? "http://127.0.0.1:8011";

async function syntheticPackageId(
  request: APIRequestContext,
): Promise<string> {
  const response = await request.get(`${apiBase}/v1/packages`);
  expect(response.ok()).toBeTruthy();
  const packages = (await response.json()) as Array<{
    id: string;
    external_key: string;
    package_version: number;
  }>;
  const synthetic = packages.find(
    (item) =>
      item.external_key === "horizon-2026-acquisition" && item.package_version === 1,
  );
  expect(synthetic, "replay-safe Horizon synthetic package should be seeded").toBeDefined();
  return synthetic?.id ?? "";
}

function expectNoRuntimeErrors(page: Page): string[] {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(`pageerror: ${error.message}`));
  page.on("console", (message) => {
    if (message.type() === "error") errors.push(`console: ${message.text()}`);
  });
  return errors;
}

test("renders the live Entity Control Center and its evidence surfaces", async ({ page }, testInfo) => {
  const runtimeErrors = expectNoRuntimeErrors(page);
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Consolidated acquisition" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Account mapping ledger" })).toBeVisible();
  await expect(page.getByRole("heading", { name: /Blockers/ })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Launch sequence" })).toBeVisible();
  await expect(page.getByText("Hash chain verified")).toBeVisible();
  await expect(page.getByText("Phase 1", { exact: true })).toBeVisible();
  await expect(page.getByText("In Progress", { exact: true })).toBeVisible();
  await expect(page.getByText("Data preparation only", { exact: true })).toBeVisible();
  await expect(page.getByText("Synthetic data", { exact: true })).toBeVisible();
  await expect(page.getByText("Sample data", { exact: true })).toBeVisible();
  await expect(page.getByText("Intercompany eliminations")).toBeVisible();
  await expect(page.getByRole("heading", { name: /acquisition package is ready|one decision turns the package ready/i })).toBeVisible();
  await expect(page.getByText("Problem", { exact: true })).toBeVisible();
  await expect(page.getByText("User", { exact: true })).toBeVisible();
  await expect(page.getByText("Outcome", { exact: true })).toBeVisible();

  await page.getByRole("searchbox", { name: "Search account mappings" }).fill("HZ-101");
  await expect(page.getByText("Operating Cash", { exact: true })).toBeVisible();
  await expect(page.getByText("1 of 18")).toBeVisible();
  await page.getByRole("searchbox", { name: "Search account mappings" }).clear();

  await page.getByRole("button", { name: /Northstar Apartments/ }).click();
  await expect(page.getByRole("heading", { name: "Northstar Apartments" })).toBeVisible();
  await expect(page.getByText("6 of 6")).toBeVisible();
  await page.getByRole("button", { name: /All entities/ }).click();

  if (testInfo.project.name === "desktop-chromium") {
    await page.getByRole("button", { name: /Open evidence ledger/ }).click();
    await expect(page.getByRole("heading", { name: "Audit evidence ledger" })).toBeVisible();
    await expect(page.getByText(/Audit chain verified/)).toBeVisible();
    await page.getByText("Inspect event evidence").first().click();
    await expect(page.getByText("Previous hash", { exact: true }).first()).toBeVisible();
    await expect(page.getByText("Payload", { exact: true }).first()).toBeVisible();
    await page.getByRole("button", { name: "Done" }).click();
  }

  const accessibility = await new AxeBuilder({ page }).analyze();
  expect(accessibility.violations.filter((violation) => ["serious", "critical"].includes(violation.impact ?? ""))).toEqual([]);
  expect(runtimeErrors).toEqual([]);
});

test("keeps the guided story keyboard-usable and contained on desktop and mobile", async ({ page }) => {
  const runtimeErrors = expectNoRuntimeErrors(page);
  await page.goto("/");
  await page.getByRole("button", { name: "Start full tour" }).click();
  const guide = page.getByRole("complementary", { name: "Three-minute guided demo" });
  await expect(guide).toBeVisible();
  await expect(page.getByRole("heading", { name: /Acquired companies rarely/ })).toBeFocused();

  const containment = await guide.evaluate((element) => {
    const box = element.getBoundingClientRect();
    const visualViewport = window.visualViewport;
    return {
      left: box.left,
      top: box.top,
      right: box.right,
      bottom: box.bottom,
      viewportLeft: visualViewport?.offsetLeft ?? 0,
      viewportTop: visualViewport?.offsetTop ?? 0,
      viewportRight: (visualViewport?.offsetLeft ?? 0) + (visualViewport?.width ?? window.innerWidth),
      viewportBottom: (visualViewport?.offsetTop ?? 0) + (visualViewport?.height ?? window.innerHeight),
    };
  });
  expect(containment.left).toBeGreaterThanOrEqual(containment.viewportLeft);
  expect(containment.top).toBeGreaterThanOrEqual(containment.viewportTop);
  expect(containment.right).toBeLessThanOrEqual(containment.viewportRight);
  expect(containment.bottom).toBeLessThanOrEqual(containment.viewportBottom);

  await page.keyboard.press("ArrowRight");
  await expect(page.getByRole("heading", { name: /implementation specialist controls/ })).toBeVisible();
  await page.keyboard.press("ArrowRight");
  await expect(page.getByRole("heading", { name: /Review the one decision left|The final mapping is approved/ })).toBeVisible();
  await expect(page.getByRole("searchbox", { name: "Search account mappings" })).toHaveValue("HZ-115");
  await expect(page.getByRole("button", { name: "Hide mapping evidence for HZ-115" })).toBeVisible();

  await page.keyboard.press("Escape");
  await expect(guide).toBeHidden();
  await page.getByRole("button", { name: "3-minute demo" }).click();
  await page.getByRole("button", { name: /Next guided demo step/ }).click();
  await expect(page.getByRole("heading", { name: /implementation specialist controls/ })).toBeVisible();
  await page.getByRole("button", { name: "Restart guide" }).click();
  await expect(page.getByRole("heading", { name: /Acquired companies rarely/ })).toBeVisible();
  expect(runtimeErrors).toEqual([]);
});

test("guides the final evidence decision through READY and preserves its audit proof", async ({ page, request }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop-chromium", "One persistent synthetic mutation is sufficient.");
  const packageId = await syntheticPackageId(request);
  const mappingsBeforeResponse = await request.get(`${apiBase}/v1/packages/${packageId}/mappings`);
  const sourceAccountsBeforeResponse = await request.get(`${apiBase}/v1/packages/${packageId}/source-accounts`);
  const blockersBeforeResponse = await request.get(`${apiBase}/v1/packages/${packageId}/blockers`);
  const auditBeforeResponse = await request.get(`${apiBase}/v1/packages/${packageId}/audit-events`);
  const readinessBeforeResponse = await request.get(`${apiBase}/v1/packages/${packageId}/readiness`);
  const sequenceBeforeResponse = await request.get(`${apiBase}/v1/packages/${packageId}/sequence`);
  expect(mappingsBeforeResponse.ok()).toBeTruthy();
  expect(sourceAccountsBeforeResponse.ok()).toBeTruthy();
  expect(blockersBeforeResponse.ok()).toBeTruthy();
  expect(auditBeforeResponse.ok()).toBeTruthy();
  expect(readinessBeforeResponse.ok()).toBeTruthy();
  expect(sequenceBeforeResponse.ok()).toBeTruthy();
  const mappingsBefore = await mappingsBeforeResponse.json() as Array<{ id: string; source_account_code: string; status: string; confidence: number; approved_by: string | null }>;
  const sourceAccountsBefore = await sourceAccountsBeforeResponse.json() as Array<{ code: string; approved_mapping: object | null }>;
  const blockersBefore = await blockersBeforeResponse.json() as Array<{ state: string; source_account_id: string | null }>;
  const auditBefore = await auditBeforeResponse.json() as Array<{ event_type: string; actor_id: string }>;
  const readinessBefore = await readinessBeforeResponse.json() as { evaluation_id: string; status: string };
  const sequenceBefore = await sequenceBeforeResponse.json() as { steps: Array<{ state: string }> };
  const candidate = mappingsBefore.find((mapping) => mapping.source_account_code === "HZ-115" && mapping.status === "SUGGESTED");
  test.skip(readinessBefore.status === "DATA_PREPARATION_READY", "The preserved guided demo has already been completed; use the documented reset to replay the mutation.");
  expect(candidate, "HZ-115 should be the final suggested mapping").toBeDefined();
  if (!candidate) throw new Error("HZ-115 guided candidate missing");
  expect(sourceAccountsBefore.filter((account) => account.approved_mapping !== null)).toHaveLength(17);
  expect(blockersBefore.filter((blocker) => blocker.state === "OPEN")).toHaveLength(1);
  expect(readinessBefore.status).toBe("NOT_READY");
  expect(sequenceBefore.steps.filter((step) => step.state === "COMPLETE")).toHaveLength(6);
  expect(sequenceBefore.steps.filter((step) => step.state === "READY")).toHaveLength(1);
  expect(sequenceBefore.steps.filter((step) => step.state === "BLOCKED")).toHaveLength(8);

  await page.goto("/");
  await expect(page.getByRole("heading", { name: "One decision turns the package ready" })).toBeVisible();
  await expect(page.getByText("17/18", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Review final decision" }).click();
  await expect(page.getByRole("button", { name: /Horizon Group/ })).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByRole("heading", { name: "Review the one decision left" })).toBeVisible();
  await expect(page.getByRole("searchbox", { name: "Search account mappings" })).toHaveValue("HZ-115");
  await expect(page.getByRole("button", { name: "Hide mapping evidence for HZ-115" })).toBeVisible();
  await expect(page.getByText("Trade receivables map to accounts receivable.")).toBeVisible();
  await page.getByRole("button", { name: "Review & approve" }).first().click();
  await page.getByRole("textbox", { name: "Human reviewer ID" }).fill("guided-demo-browser-reviewer");
  await page.getByRole("textbox", { name: "Decision note" }).fill("Live guided-demo verification: reviewed the synthetic source name, asset classification, opening balance, and Accounts Receivable target.");
  await page.getByRole("button", { name: "Approve 1" }).click();
  await expect(page.getByRole("status")).toContainText("1 mapping decision recorded");
  await expect(page.getByRole("heading", { name: "The acquisition package is ready" })).toBeVisible();
  await expect(page.getByText("18/18", { exact: true })).toBeVisible();

  const mappingsAfterResponse = await request.get(`${apiBase}/v1/packages/${packageId}/mappings`);
  const blockersAfterResponse = await request.get(`${apiBase}/v1/packages/${packageId}/blockers`);
  const auditAfterResponse = await request.get(`${apiBase}/v1/packages/${packageId}/audit-events`);
  const readinessAfterResponse = await request.get(`${apiBase}/v1/packages/${packageId}/readiness`);
  const sequenceAfterResponse = await request.get(`${apiBase}/v1/packages/${packageId}/sequence`);
  const mappingsAfter = await mappingsAfterResponse.json() as Array<{ id: string; status: string; approved_by: string | null }>;
  const blockersAfter = await blockersAfterResponse.json() as Array<{ state: string }>;
  const auditAfter = await auditAfterResponse.json() as Array<{ event_type: string; actor_id: string }>;
  const readinessAfter = await readinessAfterResponse.json() as { evaluation_id: string; status: string };
  const sequenceAfter = await sequenceAfterResponse.json() as { steps: Array<{ state: string }> };
  const approved = mappingsAfter.find((mapping) => mapping.id === candidate.id);
  expect(approved).toMatchObject({ status: "APPROVED", approved_by: "guided-demo-browser-reviewer" });
  expect(blockersAfter.filter((blocker) => blocker.state === "OPEN")).toHaveLength(0);
  expect(auditAfter.length).toBeGreaterThan(auditBefore.length);
  expect(auditAfter.some((event) => event.event_type === "MAPPING_APPROVED" && event.actor_id === "guided-demo-browser-reviewer")).toBeTruthy();
  expect(readinessAfter.evaluation_id).not.toBe(readinessBefore.evaluation_id);
  expect(readinessAfter.status).toBe("DATA_PREPARATION_READY");
  expect(sequenceAfter.steps.every((step) => step.state === "COMPLETE")).toBeTruthy();

  await page.getByRole("button", { name: "Go to 4 · Control consequence" }).click();
  await expect(page.getByRole("heading", { name: "The evidence-backed blocker cleared" })).toBeVisible();
  await expect(page.getByText("No open exceptions")).toBeVisible();
  await page.getByRole("button", { name: "Go to 5 · Operational outcome" }).click();
  await expect(page.getByRole("heading", { name: "Every dependency step is complete" })).toBeVisible();
  await expect(page.getByText("15/15")).toBeVisible();
  await page.getByRole("button", { name: "Go to 6 · Defensible proof" }).click();
  await page.getByRole("button", { name: "Open audit ledger" }).click();
  await expect(page.getByRole("heading", { name: "Audit evidence ledger" })).toBeVisible();
  await expect(page.getByText(/Audit chain verified/)).toBeVisible();
  await expect(page.getByText("guided-demo-browser-reviewer", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Done" }).click();

  await page.getByRole("button", { name: "Refresh workspace" }).click();
  await expect(page.getByText("Workspace refreshed from the audit-backed API.")).toBeVisible();
  const row = page.locator("tbody tr").filter({ hasText: "HZ-115" }).first();
  await expect(row.getByText("Approved", { exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "The acquisition package is ready" })).toBeVisible();
});

test("keeps Phase 1, In Progress, and synthetic boundaries visible across responsive widths", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop-chromium", "One Chromium context covers the responsive width matrix.");
  for (const width of [1024, 800, 412]) {
    await page.setViewportSize({ width, height: 900 });
    await page.goto("/");
    await expect(page.getByText("Phase 1", { exact: true })).toBeVisible();
    await expect(page.getByText("In Progress", { exact: true })).toBeVisible();
    await expect(page.getByText("Data preparation only", { exact: true })).toBeVisible();
    await expect(page.getByText("Synthetic data", { exact: true })).toBeVisible();
  }
});

test("contains horizontal data tables without causing page overflow", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "mobile-chromium", "Mobile viewport assertion.");
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Consolidated acquisition" })).toBeVisible();
  const dimensions = await page.evaluate(async () => {
    window.scrollTo({ left: 999, top: 0 });
    await new Promise<void>((resolve) => requestAnimationFrame(() => resolve()));
    const app = document.querySelector(".app-shell")?.getBoundingClientRect();
    const tableRegion = document.querySelector(".table-scroll");
    return {
      bodyWidth: document.body.scrollWidth,
      viewportWidth: document.documentElement.clientWidth,
      horizontalPageScroll: window.scrollX,
      appLeft: app?.left ?? -1,
      appRight: app?.right ?? -1,
      tableClientWidth: tableRegion?.clientWidth ?? 0,
      tableScrollWidth: tableRegion?.scrollWidth ?? 0,
      tableOverflow: tableRegion ? getComputedStyle(tableRegion).overflowX : "missing",
    };
  });
  expect(dimensions.bodyWidth).toBeLessThanOrEqual(dimensions.viewportWidth);
  expect(dimensions.horizontalPageScroll).toBe(0);
  expect(dimensions.appLeft).toBe(0);
  expect(dimensions.appRight).toBeLessThanOrEqual(dimensions.viewportWidth);
  expect(dimensions.tableScrollWidth).toBeGreaterThan(dimensions.tableClientWidth);
  expect(dimensions.tableOverflow).toBe("auto");
  await expect(page.getByRole("searchbox", { name: "Search account mappings" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Launch sequence" })).toBeVisible();
});

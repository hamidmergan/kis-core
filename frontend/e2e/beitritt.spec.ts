import { test, expect, request as playwrightRequest, type Page } from "@playwright/test";

/** Joining by code, the setup builds the course through the API and cleans up after itself. */

const OWNER = { username: process.env.E2E_USER ?? "a", password: process.env.E2E_PASS ?? "a" };
const BESUCHER = { username: "b", password: "b" };
const TITEL = "E2E Beitritt Kurs";

test.use({ storageState: { cookies: [], origins: [] } });

// A cold dev server plus two page loads does not fit into the default budget.
test.setTimeout(180_000);

/** Logs in and clears the welcome dialog, which a fresh profile always gets. */
async function anmelden(page: Page, konto: { username: string; password: string }) {
  await page.goto("/", { waitUntil: "domcontentloaded" });
  await page.waitForSelector("#username");
  await page.fill("#username", konto.username);
  await page.fill("#password", konto.password);
  await page.locator('button[type="submit"]').click();
  await page.waitForURL((url) => !url.pathname.includes("login"), { timeout: 30_000 });

  // It only shows once per profile, so it may or may not be there.
  const dialog = page.locator("[role=dialog]");
  if (await dialog.count()) {
    await dialog.locator("button[aria-label]").first().click();
    await expect(dialog).toHaveCount(0);
  }
}

test("Beitreten: Code von Hand einsetzen und im Modul landen", async ({ page, baseURL }) => {
  const owner = await playwrightRequest.newContext({ baseURL });
  const anmeldung = await owner.post("/auth/login", { data: OWNER });
  expect(anmeldung.ok()).toBeTruthy();

  const angelegt = await (await owner.post("/api/ai-assistant/workspaces", {
    form: { title: TITEL },
  })).json();
  // A fresh course is switched off, and a closed course shows a different card.
  await owner.patch(`/api/ai-assistant/workspaces/${angelegt.uuid}`, { data: { is_active: true } });

  const link = await (await owner.post(
    `/api/ai-assistant/workspaces/${angelegt.uuid}/access-links`,
    { data: { expires_at: null } },
  )).json();
  expect(link.code).toBeTruthy();

  try {
    await anmelden(page, BESUCHER);

    await page.getByTestId("join-open").click();

    // Upper case with a space in the middle, the way a dictated code arrives.
    const getippt = `${link.code.slice(0, 4)} ${link.code.slice(4)}`.toUpperCase();
    await page.fill("#join-module-code", getippt);
    await page.getByTestId("join-submit").click();

    // The existing enrollment card takes over.
    await page.waitForURL((url) => url.searchParams.get("code") === link.code, { timeout: 30_000 });
    await expect(page.getByRole("heading", { name: TITEL })).toBeVisible();

    // The label follows the browser language, the test marker does not.
    await page.getByTestId("enroll-submit").click();
    await page.waitForURL((url) => url.pathname.includes(angelegt.uuid), { timeout: 30_000 });

    // The course is in the list afterwards.
    await page.goto("/", { waitUntil: "domcontentloaded" });
    await expect(page.locator("tbody tr").filter({ hasText: TITEL })).toHaveCount(1);
  } finally {
    await owner.delete(`/api/ai-assistant/workspaces/${angelegt.uuid}`);
    await owner.dispose();
  }
});

test("Beitreten: unbekannter Code bleibt im Dialog stehen", async ({ page }) => {
  await anmelden(page, BESUCHER);

  await page.getByTestId("join-open").click();
  await page.fill("#join-module-code", "Hallo, hier ist der Link");
  await page.getByTestId("join-submit").click();

  await expect(page.locator("#join-module-code")).toBeVisible();
  await expect(page).toHaveURL((url) => url.searchParams.get("code") === null);
});

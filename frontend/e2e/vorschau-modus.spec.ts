import { test, expect, request as playwrightRequest } from "@playwright/test";

/**
 * Preview mode: layout only, never functions.
 *
 * Two directions of the same switch. Owners look at the student side, enrolled
 * people look at the owner side, but only in the demo course. The second test
 * sets up its own demo course through the API and clears it away again.
 */

const OWNER = { username: process.env.E2E_USER ?? "a", password: process.env.E2E_PASS ?? "a" };
const TESTER = { username: "b", password: "b" };
const WORKSPACE = process.env.E2E_WORKSPACE ?? "1ea7b2fa-b237-4bbd-801b-c9793d388984";

/**
 * Sets the demo account and hands back a function that restores the state.
 *
 * Necessary because only ONE account can be the demo account: whoever sets the
 * flag takes it away from whoever had it. Without restoring, every test run
 * would silently wipe the demo course out of the local dev environment.
 */
async function demoKontoUebernehmen(
  admin: import("@playwright/test").APIRequestContext,
  username: string,
) {
  const liste = await (await admin.get("/api/admin/users?limit=100")).json();
  const vorher = liste.users.find((u: { is_demo?: boolean }) => u.is_demo);
  const konto = liste.users.find((u: { ldap_username: string }) => u.ldap_username === username);
  await admin.post(`/api/admin/users/${konto.id}/demo`, { data: { is_demo: true } });
  return async () => {
    await admin.post(`/api/admin/users/${konto.id}/demo`, { data: { is_demo: false } });
    if (vorher && vorher.id !== konto.id) {
      await admin.post(`/api/admin/users/${vorher.id}/demo`, { data: { is_demo: true } });
    }
  };
}

const SCHALTER = '[data-tour="preview-toggle"]';
const STREIFEN = '[data-tour="preview-banner"]';
const QUELLE_HINZU = '[data-tour="add-source"]';

test.describe("Eigentümer schaut auf die Studierenden-Seite", () => {
  test("Bedienelemente verschwinden ganz, nicht nur gesperrt", async ({ page }) => {
    await page.goto(`/de/workspace/${WORKSPACE}`, { waitUntil: "domcontentloaded" });

    await expect(page.locator(SCHALTER)).toBeVisible();
    await expect(page.locator(QUELLE_HINZU)).toBeVisible();
    await expect(page.locator(STREIFEN)).toHaveCount(0);

    await page.locator(SCHALTER).click();

    await expect(page.locator(STREIFEN)).toBeVisible();
    // So sehen es Studierende wirklich: der Knopf ist weg, nicht markiert.
    await expect(page.locator(QUELLE_HINZU)).toHaveCount(0);
    await expect(page.locator(".owner-preview")).toHaveCount(0);

    await page.locator(SCHALTER).click();
    await expect(page.locator(QUELLE_HINZU)).toBeVisible();
    await expect(page.locator(STREIFEN)).toHaveCount(0);
  });

  test("der Hinweisstreifen steht auch auf Englisch da", async ({ page }) => {
    await page.goto(`/en/workspace/${WORKSPACE}`, { waitUntil: "domcontentloaded" });
    await page.locator(SCHALTER).click();
    await expect(page.locator(STREIFEN)).toContainText("students see this module");
  });
});

test.describe("Eingeschriebener schaut auf die Lehrenden-Seite", () => {
  test.use({ storageState: { cookies: [], origins: [] } });

  test("Owner-Elemente sind sichtbar, markiert und ohne Funktion", async ({ page, baseURL }) => {
    const admin = await playwrightRequest.newContext({ baseURL });
    expect((await admin.post("/auth/login", { data: OWNER })).ok()).toBeTruthy();

    const demoZurueck = await demoKontoUebernehmen(admin, OWNER.username);

    const kurs = await (await admin.post("/api/ai-assistant/workspaces", {
      form: { title: "E2E Vorschau Kurs" },
    })).json();
    // Ein frischer Kurs ist aus, und die Demo zeigt nur eingeschaltete Kurse.
    await admin.patch(`/api/ai-assistant/workspaces/${kurs.uuid}`, { data: { is_active: true } });

    try {
      await page.goto("/de/login", { waitUntil: "domcontentloaded" });
      await page.waitForSelector("#username");
      await page.fill("#username", TESTER.username);
      await page.fill("#password", TESTER.password);
      await page.click('button[type="submit"]');
      await page.waitForURL((u) => !u.pathname.includes("/login"), { timeout: 30_000 });

      // Über die Demo beitreten, dann steht der Kurs dem Tester offen.
      const beitritt = await page.request.post("/api/ai-assistant/demo/enroll", {
        data: { workspace_uuid: kurs.uuid },
      });
      expect(beitritt.ok()).toBeTruthy();

      await page.goto(`/de/workspace/${kurs.uuid}`, { waitUntil: "domcontentloaded" });

      // Im Demo-Kurs ist die Lehrenden-Vorschau von Anfang an an.
      await expect(page.locator(STREIFEN)).toBeVisible();
      const markiert = page.locator(".owner-preview");
      await expect(markiert.first()).toBeVisible();
      // Genau der Punkt der Sache: sichtbar, aber nicht bedienbar.
      await expect(markiert.first()).toHaveAttribute("inert", "");

      await page.locator(SCHALTER).click();
      await expect(page.locator(STREIFEN)).toHaveCount(0);
      await expect(page.locator(".owner-preview")).toHaveCount(0);
    } finally {
      await admin.delete(`/api/ai-assistant/workspaces/${kurs.uuid}`);
      await demoZurueck();
      await admin.dispose();
    }
  });
});

test.describe("Studierende in einem normalen Kurs", () => {
  test.use({ storageState: { cookies: [], origins: [] } });

  test("bekommen den Schalter gar nicht erst zu sehen", async ({ page }) => {
    await page.goto("/de/login", { waitUntil: "domcontentloaded" });
    await page.waitForSelector("#username");
    await page.fill("#username", TESTER.username);
    await page.fill("#password", TESTER.password);
    await page.click('button[type="submit"]');
    await page.waitForURL((u) => !u.pathname.includes("/login"), { timeout: 30_000 });

    await page.goto(`/de/workspace/${WORKSPACE}`, { waitUntil: "domcontentloaded" });
    await expect(page.locator(QUELLE_HINZU)).toHaveCount(0);
    await expect(page.locator(SCHALTER)).toHaveCount(0);
  });
});

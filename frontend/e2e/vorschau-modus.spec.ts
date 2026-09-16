import { test, expect, request as playwrightRequest } from "@playwright/test";
import { demoKontoUebernehmen } from "./_demoKonto";

/**
 * Preview mode: layout only, never functions.
 *
 * Two directions of the same switch. Owners look at the student side, enrolled
 * people look at the owner side, but only in the demo course. The second test
 * sets up its own demo course through the API and clears it away again.
 */

const OWNER = { username: process.env.E2E_USER ?? "a", password: process.env.E2E_PASS ?? "a" };
const TESTER = { username: "b", password: "b" };
// The owner preview needs aia.workspace.create, a plain account no longer gets it.
const LEHRENDE = { username: "ff", password: "ff" };
const WORKSPACE = process.env.E2E_WORKSPACE ?? "1ea7b2fa-b237-4bbd-801b-c9793d388984";

const ZAHNRAD = '[data-tour="module-settings"]';
const SCHALTER = '[data-tour="preview-toggle"]';
const STREIFEN = '[data-tour="preview-banner"]';
const QUELLE_HINZU = '[data-tour="add-source"]';
const HINWEIS = '[data-tour="staff-note"]';

/** Der Schalter sitzt in den Einstellungen, das Fenster schliesst sich beim Umschalten selbst. */
async function vorschauUmschalten(page: import("@playwright/test").Page) {
  await page.locator(ZAHNRAD).click();
  await page.locator(SCHALTER).click();
  await expect(page.locator(SCHALTER)).toHaveCount(0);
}

test.describe("Eigentümer schaut auf die Studierenden-Seite", () => {
  test("Bedienelemente verschwinden ganz, nicht nur gesperrt", async ({ page }) => {
    await page.goto(`/de/workspace/${WORKSPACE}`, { waitUntil: "domcontentloaded" });

    await expect(page.locator(QUELLE_HINZU)).toBeVisible();
    await expect(page.locator(STREIFEN)).toHaveCount(0);

    await vorschauUmschalten(page);

    await expect(page.locator(STREIFEN)).toBeVisible();
    // So sehen es Studierende wirklich: der Knopf ist weg, nicht markiert.
    await expect(page.locator(QUELLE_HINZU)).toHaveCount(0);
    await expect(page.locator(".owner-preview")).toHaveCount(0);

    await vorschauUmschalten(page);
    await expect(page.locator(QUELLE_HINZU)).toBeVisible();
    await expect(page.locator(STREIFEN)).toHaveCount(0);
  });

  test("der Hinweisstreifen steht auch auf Englisch da", async ({ page }) => {
    await page.goto(`/en/workspace/${WORKSPACE}`, { waitUntil: "domcontentloaded" });
    await vorschauUmschalten(page);
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
      await page.fill("#username", LEHRENDE.username);
      await page.fill("#password", LEHRENDE.password);
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
      await expect(page.locator(".owner-preview").first()).toHaveAttribute("inert", "");

      // Genau der Punkt der Sache: sichtbar, aber nicht bedienbar. Jedes
      // Lehrenden-Bedienelement einzeln, sonst deckt ein Treffer die anderen zu.
      for (const knopf of [QUELLE_HINZU, HINWEIS]) {
        await expect(page.locator(knopf)).toBeVisible();
        await expect(page.locator(knopf).locator("xpath=ancestor::*[@inert]")).toHaveCount(1);
      }

      // Schmal faellt die Panel-Kopfzeile weg, die Knoepfe ruecken in eine
      // eigene Zeile. Auch die muss gesperrt bleiben.
      await page.setViewportSize({ width: 390, height: 844 });
      await page.getByRole("button", { name: "Materialien", exact: true }).click();
      await expect(page.locator(QUELLE_HINZU)).toBeVisible();
      await expect(page.locator(QUELLE_HINZU).locator("xpath=ancestor::*[@inert]")).toHaveCount(1);
      await page.setViewportSize({ width: 1280, height: 720 });

      await vorschauUmschalten(page);
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
    // Erst wenn die Topbar steht, ist ein fehlender Knopf echt und kein Ladezustand.
    await page.locator(ZAHNRAD).waitFor({ timeout: 30_000 });
    const modul = await (await page.request.get(`/api/ai-assistant/workspaces/${WORKSPACE}`)).json();
    test.skip(!!modul.can_manage, "Hier verwaltet das Konto das Modul mit, dann steht ihm die Vorschau zu.");

    await expect(page.locator(QUELLE_HINZU)).toHaveCount(0);
    // Auch hinter dem Zahnrad steht die Zeile nicht.
    await page.locator(ZAHNRAD).click();
    await expect(page.locator(SCHALTER)).toHaveCount(0);
  });
});

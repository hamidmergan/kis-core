import { test, expect, request as playwrightRequest } from "@playwright/test";

/**
 * Der Weg von vorne bis hinten: ein Konto wird zum Demo-Konto, sein Kurs
 * erscheint bei einem anderen Nutzer im Demo-Fenster, laesst sich betreten und
 * ueber die Kursliste wieder verlassen. Der Aufbau passiert ueber die API,
 * damit der Test seinen Zustand selbst herstellt und hinterher aufraeumt.
 */

const DEMO_KONTO = { username: process.env.E2E_USER ?? "a", password: process.env.E2E_PASS ?? "a" };
const BESUCHER = { username: "b", password: "b" };
const TITEL = "E2E Demo Kurs";

test.use({ storageState: { cookies: [], origins: [] } });

test("Demo-Fenster: einen Kurs betreten und wieder verlassen", async ({ page, baseURL }) => {
  const admin = await playwrightRequest.newContext({ baseURL });
  const anmeldung = await admin.post("/auth/login", { data: DEMO_KONTO });
  expect(anmeldung.ok()).toBeTruthy();

  const liste = await (await admin.get("/api/admin/users?limit=100")).json();
  const konto = liste.users.find((u: { ldap_username: string }) => u.ldap_username === DEMO_KONTO.username);
  expect(konto).toBeTruthy();

  await admin.post(`/api/admin/users/${konto.id}/demo`, { data: { is_demo: true } });

  const angelegt = await (await admin.post("/api/ai-assistant/workspaces", {
    form: { title: TITEL },
  })).json();
  // Ein frischer Kurs ist ausgeschaltet, und ausgeschaltete Kurse zeigt die Demo nicht.
  await admin.patch(`/api/ai-assistant/workspaces/${angelegt.uuid}`, { data: { is_active: true } });

  try {
    await page.goto("/", { waitUntil: "domcontentloaded" });
    await page.waitForSelector("#username");
    await page.fill("#username", BESUCHER.username);
    await page.fill("#password", BESUCHER.password);
    await page.locator('button[type="submit"]').click();
    await page.waitForURL((url) => !url.pathname.includes("login"), { timeout: 30_000 });

    // Betreten im Fenster.
    await page.getByTestId("demo-open").click();
    const zeile = page.getByTestId("demo-list").locator("> div").filter({ hasText: TITEL });
    await expect(zeile).toBeVisible();
    await zeile.getByTestId("demo-join").click();
    await expect(zeile.getByTestId("demo-leave")).toBeVisible();

    // Der Kurs steht danach in der Liste.
    await page.locator('[role=dialog] button[aria-label]').click();
    const kursZeile = page.locator("tbody tr").filter({ hasText: TITEL });
    await expect(kursZeile).toHaveCount(1);

    // Verlassen ueber das Menue in der Zeile.
    await kursZeile.getByTestId("demo-row-menu").click();
    await page.getByTestId("demo-leave-row").click();
    await expect(page.locator("tbody tr").filter({ hasText: TITEL })).toHaveCount(0);
  } finally {
    await admin.delete(`/api/ai-assistant/workspaces/${angelegt.uuid}`);
    await admin.post(`/api/admin/users/${konto.id}/demo`, { data: { is_demo: false } });
    await admin.dispose();
  }
});

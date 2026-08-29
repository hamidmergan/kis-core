import { test, expect, request as playwrightRequest } from "@playwright/test";

/** A stranger redeems an access code and lands inside the app, the admin side runs through the API. */

const ADMIN = { username: process.env.E2E_USER ?? "a", password: process.env.E2E_PASS ?? "a" };
// A per-run suffix keeps this free even though account deletion never clears the LDAP entry.
const SUFFIX = Date.now().toString(36);

test.use({ storageState: { cookies: [], origins: [] } });

test("Zugangscode: ein Konto einlösen und die Startseite erreichen", async ({ page, baseURL }) => {
  const admin = await playwrightRequest.newContext({ baseURL });
  const anmeldung = await admin.post("/auth/login", { data: ADMIN });
  expect(anmeldung.ok()).toBeTruthy();

  const erstellt = await admin.post("/api/admin/access-codes", {
    data: {
      label: `E2E Zugangscode ${SUFFIX}`,
      max_uses: 2,
      valid_days: 7,
      access_days: 7,
      kis_role: "staff",
      custom_role_id: null,
    },
  });
  expect(erstellt.ok()).toBeTruthy();
  const code = await erstellt.json();

  let username = "";
  try {
    // Needs "load", not "domcontentloaded", or fills land in the DOM before hydration and never reach React state.
    await page.goto("/de/redeem", { waitUntil: "load" });
    const formular = page.getByTestId("access-code-form");
    await formular.locator("#access-code").fill(code.code);

    const [einloesung] = await Promise.all([
      page.waitForResponse((r) => r.url().includes("/access-codes/redeem") && r.request().method() === "POST"),
      formular.locator('button[type="submit"]').click(),
    ]);
    expect(einloesung.ok()).toBeTruthy();
    const antwort = await einloesung.json();
    username = antwort.username;
    expect(username).toBeTruthy();
    expect(antwort.password).toBeTruthy();

    const fertig = page.getByTestId("access-code-done");
    await expect(fertig).toBeVisible();
    await expect(fertig.getByTestId("access-code-username")).toHaveText(username);
    await expect(fertig.getByTestId("access-code-password")).toHaveText(antwort.password);

    // The done card's only button goes to "/", where the workspace list lives.
    const [kurse] = await Promise.all([
      page.waitForResponse((r) => r.url().includes("/api/ai-assistant/workspaces") && r.request().method() === "GET"),
      fertig.locator("button").click(),
    ]);
    expect(kurse.ok()).toBeTruthy();
    await expect(page).toHaveURL((url) => !url.pathname.includes("redeem") && !url.pathname.includes("login"));
    await expect(page.locator("h1").filter({ hasText: username })).toBeVisible();
  } finally {
    await admin.delete(`/api/admin/access-codes/${code.id}`);
    if (username) {
      const liste = await (await admin.get(`/api/admin/users?limit=100&q=${encodeURIComponent(username)}`)).json();
      const konto = liste.users.find((u: { ldap_username: string }) => u.ldap_username === username);
      if (konto) await admin.delete(`/api/admin/users/${konto.id}`);
    }
    await admin.dispose();
  }
});

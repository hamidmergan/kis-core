import { test, expect, request as playwrightRequest } from "@playwright/test";

/**
 * The guided tour through a course.
 *
 * The point of this test is not the wording but the anchors: it walks the
 * whole tour once, so a step that lost its `data-tour` element shows up here
 * instead of silently pointing at nothing in front of a tester.
 */

const OWNER = { username: process.env.E2E_USER ?? "a", password: process.env.E2E_PASS ?? "a" };
const WORKSPACE = process.env.E2E_WORKSPACE ?? "1ea7b2fa-b237-4bbd-801b-c9793d388984";
const POPOVER = ".driver-popover";

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

/**
 * Puts an account on a system role and hands back a function that restores it.
 *
 * The tour asks whether someone may create modules themselves, and only a real
 * role answers that. The test account keeps its own role, so it is put back.
 */
async function rolleUebernehmen(
  admin: import("@playwright/test").APIRequestContext,
  username: string,
  rolle: string,
) {
  const liste = await (await admin.get("/api/admin/users?limit=100")).json();
  const konto = liste.users.find((u: { ldap_username: string }) => u.ldap_username === username);
  const vorher = { role: konto.role, custom_role_id: konto.custom_role_id ?? null };
  await admin.post(`/api/admin/users/${konto.id}/role`, {
    data: { role: rolle, custom_role_id: null },
  });
  return async () => {
    await admin.post(`/api/admin/users/${konto.id}/role`, { data: vorher });
  };
}

/** Logging in by hand, the tests here start without a stored session. */
async function anmelden(page: import("@playwright/test").Page, name: string, passwort: string) {
  await page.goto("/de/login", { waitUntil: "domcontentloaded" });
  await page.waitForSelector("#username");
  await page.fill("#username", name);
  await page.fill("#password", passwort);
  await page.click('button[type="submit"]');
  await page.waitForURL((u) => !u.pathname.includes("/login"), { timeout: 30_000 });
}

/**
 * A throwaway demo course owned by someone else, with "b" logged in and the
 * tour mark cleared.
 *
 * The invitation only appears under exactly these conditions, and setting them
 * up per test would repeat the whole admin dance.
 */
async function alsGastImDemoKurs(
  page: import("@playwright/test").Page,
  baseURL: string | undefined,
  titel: string,
  ablauf: (kurs: { uuid: string }) => Promise<void>,
) {
  const admin = await playwrightRequest.newContext({ baseURL });
  expect((await admin.post("/auth/login", { data: OWNER })).ok()).toBeTruthy();
  const demoZurueck = await demoKontoUebernehmen(admin, OWNER.username);
  const kurs = await (await admin.post("/api/ai-assistant/workspaces", {
    form: { title: titel },
  })).json();
  await admin.patch(`/api/ai-assistant/workspaces/${kurs.uuid}`, { data: { is_active: true } });
  try {
    // Bewusst ein anderes Konto: dem Eigentümer bietet die Karte seinen
    // eigenen Kurs nicht als Demo an, das wäre auch sinnlos.
    await anmelden(page, "b", "b");
    // Der Merker haengt am Konto, also ueber die API zuruecksetzen.
    await page.request.post("/api/me/tour-seen", { data: { seen: false } });
    await ablauf(kurs);
  } finally {
    await admin.delete(`/api/ai-assistant/workspaces/${kurs.uuid}`);
    await demoZurueck();
    await admin.dispose();
  }
}

/**
 * Clicks "Weiter" at a human pace.
 *
 * The demo tour drops a click that follows the last jump within half a
 * second, that is how it swallows double clicks. A test that clicks the
 * moment the next station appears would look like exactly that.
 */
async function weiterKlicken(page: import("@playwright/test").Page) {
  await page.waitForTimeout(600);
  await page.locator(".driver-popover-next-btn").click();
}

/** Same pace for the way back, the tour swallows a quick second click there too. */
async function zurueckKlicken(page: import("@playwright/test").Page) {
  await page.waitForTimeout(600);
  await page.locator(".driver-popover-prev-btn").click();
}

async function tourOeffnen(page: import("@playwright/test").Page, locale: "de" | "en") {
  // Der Rundgang startet ueber die Adresse, im Kopfmenue haengt derselbe Weg.
  await page.goto(`/${locale}/workspace/${WORKSPACE}?tour=1`, { waitUntil: "domcontentloaded" });
  await page.locator(POPOVER).waitFor({ timeout: 30_000 });
}

test("der Rundgang läuft von vorn bis hinten durch", async ({ page }) => {
  await tourOeffnen(page, "de");

  await expect(page.locator(POPOVER)).toBeVisible();
  await expect(page.locator(POPOVER)).toContainText("Lehrenden- und Studierenden-Ansicht");

  // Durchklicken bis zum Ende, jeder Schritt muss einen sichtbaren Anker haben.
  const gesehen: string[] = [];
  for (let i = 0; i < 12; i++) {
    const titelFeld = page.locator(".driver-popover-title");
    if (await titelFeld.count() === 0) break;
    const titel = (await titelFeld.first().textContent())?.trim();
    if (titel && titel !== gesehen[gesehen.length - 1]) gesehen.push(titel);
    const weiter = page.locator(".driver-popover-next-btn");
    if (await weiter.count() === 0) break;
    const beschriftung = (await weiter.first().textContent())?.trim();
    await weiter.first().click();
    if (beschriftung === "Fertig") break;
    // Ein Schritt oeffnet die PDF, das dauert einen Moment.
    await page.waitForTimeout(800);
  }

  // Mindestens die vier Schritte, die immer da sind: Vorschau, Quellen, Quelle, Chat.
  expect(gesehen.length).toBeGreaterThanOrEqual(4);
  expect(gesehen).toContain("Die Materialien des Kurses");
  await expect(page.locator(POPOVER)).toHaveCount(0);
});

test("ein fehlender Anker bricht den Rundgang nicht", async ({ page }) => {
  // Der Anker faellt weg, sobald er auftaucht, sonst gewinnt der Start das Rennen.
  await page.addInitScript(() => {
    new MutationObserver(() => {
      document.querySelector('[data-tour="chat-input"]')?.removeAttribute("data-tour");
    }).observe(document.documentElement, { childList: true, subtree: true });
  });
  await page.goto(`/de/workspace/${WORKSPACE}?tour=1`, { waitUntil: "domcontentloaded" });
  await expect(page.locator(POPOVER)).toBeVisible({ timeout: 30_000 });
});

test("der Rundgang spricht auch Englisch", async ({ page }) => {
  await tourOeffnen(page, "en");
  await expect(page.locator(POPOVER)).toContainText("Teacher and student view");
  await expect(page.locator(".driver-popover-next-btn")).toHaveText("Next");
});

test.describe("Einstieg von der Startseite", () => {
test.use({ storageState: { cookies: [], origins: [] } });

test("Einladung auf der Startseite führt in den Rundgang", async ({ page, baseURL }) => {
  // Der Demo-Kurs wird hier selbst eingerichtet, sonst würde der Test nur
  // überspringen und damit gar nichts belegen.
  await alsGastImDemoKurs(page, baseURL, "E2E Rundgang Kurs", async () => {
    await page.goto("/de", { waitUntil: "domcontentloaded" });

    await expect(page.locator('[data-tour="tour-invite"]')).toBeVisible();
    await page.locator('[data-tour="tour-invite"]').getByRole("button", { name: "Starten", exact: true }).click();

    // Der Beitritt läuft im Hintergrund, danach steht der Kurs offen.
    await page.waitForURL(/\/workspace\/.*tour=1/, { timeout: 30_000 });
    await expect(page.locator(POPOVER)).toBeVisible({ timeout: 30_000 });
  });
});

test("ein Abbruch mittendrin lässt die Einladung stehen", async ({ page, baseURL }) => {
  // Wer den Rundgang wegklickt, hat ihn nicht gesehen: nur "Später" auf der
  // Startseite und die letzte Station nehmen die Einladung weg.
  await alsGastImDemoKurs(page, baseURL, "E2E Abbruch Kurs", async () => {
    await page.goto("/de", { waitUntil: "domcontentloaded" });
    await page.locator('[data-tour="tour-invite"]').getByRole("button", { name: "Starten", exact: true }).click();
    await page.waitForURL(/\/workspace\/.*tour=1/, { timeout: 30_000 });
    await expect(page.locator(POPOVER)).toBeVisible({ timeout: 30_000 });

    // Eine Station weiter und dann raus, so sieht ein ungeduldiger Abbruch aus.
    const stand = await page.locator(".driver-popover-progress-text").textContent();
    await weiterKlicken(page);
    await page.waitForFunction(
      (alt) => document.querySelector(".driver-popover-progress-text")?.textContent !== alt,
      stand,
      { timeout: 20_000 },
    );
    await page.keyboard.press("Escape");
    await expect(page.locator(POPOVER)).toHaveCount(0);

    expect((await (await page.request.get("/api/me")).json()).tour_seen_at).toBeNull();
    await page.goto("/de", { waitUntil: "domcontentloaded" });
    await expect(page.locator('[data-tour="tour-invite"]')).toBeVisible();
  });
});

test("\"Ausblenden\" nimmt die Einladung weg", async ({ page, baseURL }) => {
  await alsGastImDemoKurs(page, baseURL, "E2E Ausblenden Kurs", async () => {
    await page.goto("/de", { waitUntil: "domcontentloaded" });
    await page.locator('[data-tour="tour-invite"]').getByRole("button", { name: "Ausblenden" }).click();
    await expect(page.locator('[data-tour="tour-invite"]')).toHaveCount(0);

    await page.goto("/de", { waitUntil: "domcontentloaded" });
    await expect(page.locator('[data-tour="tour-invite"]')).toHaveCount(0);
  });
});
});

test.describe("Merker am Konto", () => {
  test.use({ storageState: { cookies: [], origins: [] } });

  test("überlebt einen Browserwechsel, lässt sich aber zurücksetzen", async ({ page }) => {
    await anmelden(page, "b", "b");

    await page.request.post("/api/me/tour-seen", { data: { seen: true } });
    let konto = await (await page.request.get("/api/me")).json();
    expect(konto.tour_seen_at).not.toBeNull();

    // Ohne Speicher im Browser: frischer Kontext, der Merker muss trotzdem stehen.
    await page.context().clearCookies();
    await anmelden(page, "b", "b");
    konto = await (await page.request.get("/api/me")).json();
    expect(konto.tour_seen_at).not.toBeNull();

    // Und wieder freischalten, damit man den Rundgang erneut angeboten bekommt.
    await page.request.post("/api/me/tour-seen", { data: { seen: false } });
    konto = await (await page.request.get("/api/me")).json();
    expect(konto.tour_seen_at).toBeNull();
  });
});

test.describe("Rundgang im Demo-Modul", () => {
  test("alle 16 Stationen finden ihr Ziel", async ({ page }) => {
    const kurse = await (await page.request.get("/api/ai-assistant/demo/workspaces")).json();
    const kurs = kurse.find((k: { owned: boolean }) => !k.owned);
    test.skip(!kurs, "In dieser Umgebung gibt es keinen fremden Demo-Kurs.");

    // Denselben Weg nehmen wie die Einladung auf der Startseite: beitreten, dann rein.
    await page.request.post("/api/ai-assistant/demo/enroll", { data: { workspace_uuid: kurs.uuid } });
    await page.request.post("/api/me/tour-seen", { data: { seen: false } });
    await page.goto(`/de/workspace/${kurs.uuid}?tour=1`, { waitUntil: "domcontentloaded" });
    await page.locator(POPOVER).waitFor({ timeout: 30_000 });

    const ohneZiel: string[] = [];
    const titel: string[] = [];
    for (let i = 0; i < 20; i++) {
      const stand = await page.locator(".driver-popover-progress-text").textContent();
      titel.push(((await page.locator(".driver-popover-title").textContent()) ?? "").trim());
      // Ein Schritt ohne Anker bekommt von driver.js ein leeres Hilfs-Element,
      // ein Schritt mit Anker traegt dagegen sein data-tour. Genau daran haengt
      // dieser Test: eine Station, deren Anker verschwunden ist, faellt auf.
      const zeigtAufAnker = await page
        .locator(".driver-active-element")
        .evaluateAll((els) => els.some((e) => e.hasAttribute("data-tour")));
      if (!zeigtAufAnker) ohneZiel.push(titel[titel.length - 1]);
      const weiter = page.locator(".driver-popover-next-btn");
      const beschriftung = (await weiter.textContent())?.trim();
      await weiterKlicken(page);
      if (beschriftung === "Fertig") break;
      await page
        .waitForFunction(
          (alt) => document.querySelector(".driver-popover-progress-text")?.textContent !== alt,
          stand,
          { timeout: 20_000 },
        )
        .catch(() => {});
    }

    expect(titel).toHaveLength(16);
    expect(titel[0]).toBe("Willkommen im Demo-Modul");
    expect(titel).toContain("Das Glossar");
    expect(titel).toContain("Video mit Transkript");
    // Begruessung und Schluss stehen bewusst in der Mitte, alles dazwischen zeigt auf etwas.
    expect(ohneZiel).toEqual(["Willkommen im Demo-Modul", "Jetzt bist du dran"]);
    await expect(page.locator(POPOVER)).toHaveCount(0);

    // Bis zum Schluss durchgeklickt, das und nur das setzt den Merker.
    expect((await (await page.request.get("/api/me")).json()).tour_seen_at).not.toBeNull();
    await page.request.post("/api/me/tour-seen", { data: { seen: false } });
  });

  test("die Häkchen-Station findet die PDF auch in einem zugeklappten Kapitel", async ({ page }) => {
    const kurse = await (await page.request.get("/api/ai-assistant/demo/workspaces")).json();
    const kurs = kurse.find((k: { owned: boolean }) => !k.owned);
    test.skip(!kurs, "In dieser Umgebung gibt es keinen fremden Demo-Kurs.");

    await page.request.post("/api/ai-assistant/demo/enroll", { data: { workspace_uuid: kurs.uuid } });
    const detail = await (await page.request.get(`/api/ai-assistant/workspaces/${kurs.uuid}`)).json();
    const kapitel: string[] = (detail.chapters ?? []).map((c: { uuid: string }) => c.uuid);
    test.skip(kapitel.length === 0, "Der Demo-Kurs hat keine Kapitel.");

    // Alle Kapitel zu, so wie jemand die Liste beim letzten Besuch hinterlassen
    // haben kann. Die Zeile der PDF steht dann gar nicht auf der Seite.
    await page.addInitScript(
      ([schluessel, wert]) => { localStorage.setItem(schluessel, wert); },
      [`kis-chapters-closed-${kurs.uuid}`, JSON.stringify(kapitel)] as const,
    );
    await page.goto(`/de/workspace/${kurs.uuid}?tour=1`, { waitUntil: "domcontentloaded" });
    await page.locator(POPOVER).waitFor({ timeout: 30_000 });

    for (let i = 0; i < 20; i++) {
      const titel = ((await page.locator(".driver-popover-title").textContent()) ?? "").trim();
      if (titel.startsWith("Häkchen")) break;
      const stand = await page.locator(".driver-popover-progress-text").textContent();
      await weiterKlicken(page);
      await page
        .waitForFunction(
          (alt) => document.querySelector(".driver-popover-progress-text")?.textContent !== alt,
          stand,
          { timeout: 20_000 },
        )
        .catch(() => {});
    }

    // Der Rundgang hat das Kapitel aufgeklappt und zeigt auf den Haken der PDF.
    await expect(
      page.getByRole("button", { name: "Kapitel zuklappen" }).filter({ hasText: "Einheit 1" }),
    ).toHaveCount(1);
    const haken = page
      .locator('[data-tour="source-row"]', { hasText: "DEMO_Folien_01" })
      .locator('[data-tour="source-check"]');
    await expect(haken).toHaveClass(/driver-active-element/);
    await expect(haken).toBeInViewport();
    // Und nur diese eine PDF ist angehakt, so wie der Text der Station es sagt.
    await expect(haken).toHaveAttribute("aria-label", "Material abwählen");
    await expect(page.locator('[data-tour="source-check"][aria-label="Material abwählen"]')).toHaveCount(1);
  });

  test("ein Doppelklick auf Weiter überspringt keine Station", async ({ page }) => {
    const kurse = await (await page.request.get("/api/ai-assistant/demo/workspaces")).json();
    const kurs = kurse.find((k: { owned: boolean }) => !k.owned);
    test.skip(!kurs, "In dieser Umgebung gibt es keinen fremden Demo-Kurs.");

    await page.request.post("/api/ai-assistant/demo/enroll", { data: { workspace_uuid: kurs.uuid } });
    await page.goto(`/de/workspace/${kurs.uuid}?tour=1`, { waitUntil: "domcontentloaded" });
    await page.locator(POPOVER).waitFor({ timeout: 30_000 });

    const weiter = page.locator(".driver-popover-next-btn");
    const stand = page.locator(".driver-popover-progress-text");
    // A real double click hits the same spot again blindly, without waiting for
    // a button, so the second one goes in as raw mouse events.
    const doppelklick = async () => {
      const box = (await weiter.boundingBox())!;
      await weiterKlicken(page);
      await page.waitForTimeout(120);
      await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2);
    };

    // Station 3 steht sofort, Station 7 oeffnet erst die PDF. Beide Male darf
    // der zweite Klick keine Station ueberspringen, sonst fehlt deren Vorbereitung.
    await doppelklick();
    await expect(stand).toHaveText("Schritt 2 von 16");
    await page.waitForTimeout(700);
    await expect(stand).toHaveText("Schritt 2 von 16");
    await doppelklick();
    await expect(stand).toHaveText("Schritt 3 von 16");
    for (let erwartet = 4; erwartet <= 6; erwartet++) {
      await weiterKlicken(page);
      await expect(stand).toHaveText(`Schritt ${erwartet} von 16`);
    }
    await doppelklick();
    await expect(stand).toHaveText("Schritt 7 von 16");
    await expect(page.locator(".driver-popover-title")).toHaveText("Text markieren");
    await expect(page.locator('[data-tour="pdf-viewer"].driver-active-element')).toHaveCount(1);
    await page.waitForTimeout(700);
    await expect(stand).toHaveText("Schritt 7 von 16");
    await expect(weiter).toBeEnabled();
  });

  test("auf schmalen Bildschirmen holt die Chat-Station den Chat nach vorn", async ({ page }) => {
    const kurse = await (await page.request.get("/api/ai-assistant/demo/workspaces")).json();
    const kurs = kurse.find((k: { owned: boolean }) => !k.owned);
    test.skip(!kurs, "In dieser Umgebung gibt es keinen fremden Demo-Kurs.");

    await page.request.post("/api/ai-assistant/demo/enroll", { data: { workspace_uuid: kurs.uuid } });
    // Schmal genug fuer die eine Spalte, dort liegen die Bereiche uebereinander.
    await page.setViewportSize({ width: 700, height: 900 });
    await page.goto(`/de/workspace/${kurs.uuid}?tour=1`, { waitUntil: "domcontentloaded" });
    await page.locator(POPOVER).waitFor({ timeout: 30_000 });

    // Bis zur Chat-Station klicken, die Station davor schiebt das Studio nach vorn.
    for (let i = 0; i < 20; i++) {
      const titel = ((await page.locator(".driver-popover-title").textContent()) ?? "").trim();
      if (titel.startsWith("Francis")) break;
      const stand = await page.locator(".driver-popover-progress-text").textContent();
      await weiterKlicken(page);
      await page
        .waitForFunction(
          (alt) => document.querySelector(".driver-popover-progress-text")?.textContent !== alt,
          stand,
          { timeout: 20_000 },
        )
        .catch(() => {});
    }

    await expect(page.locator(".driver-popover-progress-text")).toHaveText("Schritt 12 von 16");
    await expect(page.locator('[data-tour="chat-panel"]')).toBeVisible();
    await expect(page.locator('[data-tour="studio-panel"]')).toBeHidden();
  });

  test("auf schmalen Bildschirmen holt der Weg zurück das Transkript wieder nach vorn", async ({ page }) => {
    const kurse = await (await page.request.get("/api/ai-assistant/demo/workspaces")).json();
    const kurs = kurse.find((k: { owned: boolean }) => !k.owned);
    test.skip(!kurs, "In dieser Umgebung gibt es keinen fremden Demo-Kurs.");

    await page.request.post("/api/ai-assistant/demo/enroll", { data: { workspace_uuid: kurs.uuid } });
    await page.setViewportSize({ width: 700, height: 900 });
    await page.goto(`/de/workspace/${kurs.uuid}?tour=1`, { waitUntil: "domcontentloaded" });
    await page.locator(POPOVER).waitFor({ timeout: 30_000 });

    // Bis zu den Notizen, die das Studio ueber das Transkript schieben.
    for (let i = 0; i < 20; i++) {
      const titel = ((await page.locator(".driver-popover-title").textContent()) ?? "").trim();
      if (titel === "Die Notizen") break;
      const stand = await page.locator(".driver-popover-progress-text").textContent();
      await weiterKlicken(page);
      await page
        .waitForFunction(
          (alt) => document.querySelector(".driver-popover-progress-text")?.textContent !== alt,
          stand,
          { timeout: 20_000 },
        )
        .catch(() => {});
    }
    await expect(page.locator('[data-tour="studio-panel"]')).toBeVisible();

    await zurueckKlicken(page);

    // Ohne eigenes Vorbereiten bliebe das Studio vorn und der Rundgang zeigte
    // auf die Notiz im verdeckten Bereich, die auf dem Telefon niemand sieht.
    await expect(page.locator(".driver-popover-title")).toHaveText("Abschnitt als Notiz");
    await expect(page.locator('[data-tour="studio-panel"]')).toBeHidden();
    // Das Symbol gibt es je Absatz, gemeint ist das eine, auf das gezeigt wird.
    const notizSymbol = page.locator('[data-tour="transcript-note"].driver-active-element');
    await expect(notizSymbol).toHaveCount(1);
    await expect(notizSymbol).toBeVisible();
  });
});

test.describe("Rundgang-Link ohne vorherige Einschreibung", () => {
  test.use({ storageState: { cookies: [], origins: [] } });

  test("tritt selbst bei, statt die Person abzuweisen", async ({ page, baseURL }) => {
    // Ein eigener Wegwerf-Kurs, damit dieser Test von keiner Voreinschreibung
    // im geteilten Demo-Kurs abhaengt und keine hinterlaesst.
    const admin = await playwrightRequest.newContext({ baseURL });
    expect((await admin.post("/auth/login", { data: OWNER })).ok()).toBeTruthy();
    const demoZurueck = await demoKontoUebernehmen(admin, OWNER.username);
    const kurs = await (await admin.post("/api/ai-assistant/workspaces", {
      form: { title: "E2E Direkteinstieg Kurs" },
    })).json();
    await admin.patch(`/api/ai-assistant/workspaces/${kurs.uuid}`, { data: { is_active: true } });

    try {
      await anmelden(page, "b", "b");

      // Bewusst NICHT vorher beigetreten: genau das soll der Aufruf selbst erledigen.
      await page.goto(`/de/workspace/${kurs.uuid}?tour=1`, { waitUntil: "domcontentloaded" });
      await expect(page.locator(POPOVER)).toBeVisible({ timeout: 30_000 });

      const eingeschrieben = await (await page.request.get("/api/ai-assistant/demo/workspaces"))
        .json()
        .then((liste: { uuid: string; joined: boolean }[]) =>
          liste.find((k) => k.uuid === kurs.uuid)?.joined);
      expect(eingeschrieben).toBe(true);
    } finally {
      await admin.delete(`/api/ai-assistant/workspaces/${kurs.uuid}`);
      await demoZurueck();
      await admin.dispose();
    }
  });
});

test.describe("Rundgang für Studierende", () => {
  test.use({ storageState: { cookies: [], origins: [] } });

  test("ohne das Recht Module anzulegen fallen die Lehrenden-Stationen weg", async ({ page, baseURL }) => {
    const admin = await playwrightRequest.newContext({ baseURL });
    expect((await admin.post("/auth/login", { data: OWNER })).ok()).toBeTruthy();
    const rolleZurueck = await rolleUebernehmen(admin, "b", "user");

    try {
      await anmelden(page, "b", "b");
      const kurse = await (await page.request.get("/api/ai-assistant/demo/workspaces")).json();
      const kurs = kurse.find((k: { owned: boolean }) => !k.owned);
      test.skip(!kurs, "In dieser Umgebung gibt es keinen fremden Demo-Kurs.");

      await page.request.post("/api/ai-assistant/demo/enroll", { data: { workspace_uuid: kurs.uuid } });
      await page.request.post("/api/me/tour-seen", { data: { seen: false } });
      await page.goto(`/de/workspace/${kurs.uuid}?tour=1`, { waitUntil: "domcontentloaded" });
      await page.locator(POPOVER).waitFor({ timeout: 30_000 });

      // Das Auge fuehrt auf die Lehrenden-Seite, die diese Person nie bekommt.
      await expect(page.locator('[data-tour="preview-toggle"]')).toHaveCount(0);
      await expect(page.locator('[data-tour="add-source"]')).toHaveCount(0);
      // Eine Station weniger als bei Lehrenden, das Hochladen faellt weg.
      await expect(page.locator(".driver-popover-progress-text")).toHaveText("Schritt 1 von 15");

      // Der Hinweis steht als zweite Station, ein Klick reicht dorthin.
      const stand = await page.locator(".driver-popover-progress-text").textContent();
      await weiterKlicken(page);
      await page
        .waitForFunction(
          (alt) => document.querySelector(".driver-popover-progress-text")?.textContent !== alt,
          stand,
          { timeout: 20_000 },
        )
        .catch(() => {});

      // Same station, but with the text written for readers.
      await expect(page.locator(".driver-popover-title")).toHaveText("Der Hinweis deiner Lehrenden");
      await expect(page.locator(".driver-popover")).not.toContainText("eigenes Modul");
    } finally {
      await rolleZurueck();
      await admin.dispose();
    }
  });
});

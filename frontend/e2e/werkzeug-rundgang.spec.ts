import { test, expect } from "@playwright/test";

/**
 * The guided tour through the tools.
 *
 * Like the tour through a course this test is not about the wording but about
 * the anchors: it walks every station once, so a tool page that lost its
 * `data-tour` shows up here instead of in front of a tester. It also watches
 * the jumps, because this tour changes the page under itself.
 */

const POPOVER = ".driver-popover";
const MENUE = 'button[aria-haspopup="menu"]';
const RUNDGANG_EINTRAG = '[data-tour="tools-tour-start"]';

/** The stations in the order of the sidebar, with the anchor each one points at. */
const STATIONEN = [
  { anker: "tools-sidebar", route: null },
  { anker: "tool-translation", route: "/tools/translate" },
  { anker: "tool-interpreter", route: "/tools/interpreter" },
  { anker: "tool-tts", route: "/tools/tts" },
  { anker: "tool-transcription", route: "/tools/stt" },
  { anker: "tool-image", route: "/tools/image" },
  { anker: "tool-summary", route: "/tools/summarize" },
  { anker: "tool-screencast", route: "/tools/screencast" },
  { anker: "tool-glossary", route: "/tools/glossary" },
  { anker: "jobs-entry", route: null },
];

/** Clicks at a human pace, a click within half a second of a jump counts as a double click. */
async function weiterKlicken(page: import("@playwright/test").Page) {
  await page.waitForTimeout(700);
  await page.locator(".driver-popover-next-btn").click();
}

async function zurueckKlicken(page: import("@playwright/test").Page) {
  await page.waitForTimeout(700);
  await page.locator(".driver-popover-prev-btn").click();
}

async function rundgangStarten(page: import("@playwright/test").Page, locale: "de" | "en" = "de") {
  await page.goto(`/${locale}/tools/translate`, { waitUntil: "domcontentloaded" });
  // The sidebar only appears once permissions and tools are in, before that the menu is not clickable either.
  await page.locator('[data-tour="tools-sidebar"]').waitFor({ timeout: 30_000 });
  await page.locator(MENUE).first().click();
  await page.locator(RUNDGANG_EINTRAG).click();
  await page.locator(POPOVER).waitFor({ timeout: 30_000 });
}

/** Waits until the ring sits on the expected anchor, the jump to a tool takes a moment. */
async function stationErwarten(page: import("@playwright/test").Page, anker: string) {
  await expect(page.locator(`.driver-active-element[data-tour="${anker}"]`)).toBeVisible({
    timeout: 20_000,
  });
}

/** The welcome dialog sits over the start page in a fresh browser, nothing behind it is clickable. */
async function willkommenSchliessen(page: import("@playwright/test").Page) {
  const dialog = page.locator('[role="dialog"]');
  try {
    await dialog.waitFor({ state: "visible", timeout: 5_000 });
    await dialog.getByRole("button").last().click();
    await dialog.waitFor({ state: "hidden", timeout: 5_000 });
  } catch {
    /* Auf diesem Konto war der Gruß schon weg. */
  }
}

test("der Rundgang läuft von der Leiste bis zu den Aufträgen durch", async ({ page }) => {
  await rundgangStarten(page);

  for (const [i, station] of STATIONEN.entries()) {
    await stationErwarten(page, station.anker);
    await expect(page.locator(`${POPOVER} .driver-popover-title`)).not.toBeEmpty();
    if (station.route) expect(page.url()).toContain(station.route);
    if (i < STATIONEN.length - 1) await weiterKlicken(page);
  }

  await page.waitForTimeout(700);
  await page.locator(".driver-popover-next-btn").click();
  await expect(page.locator(POPOVER)).toHaveCount(0);
});

test("der Weg zurück holt das vorherige Werkzeug wieder her", async ({ page }) => {
  await rundgangStarten(page);
  // Wait for each station, a click in the middle of a jump is swallowed on purpose.
  for (const anker of ["tool-translation", "tool-interpreter", "tool-tts", "tool-transcription"]) {
    await weiterKlicken(page);
    await stationErwarten(page, anker);
  }

  await zurueckKlicken(page);
  await stationErwarten(page, "tool-tts");
  expect(page.url()).toContain("/tools/tts");
});

test("der Rundgang spricht auch Englisch", async ({ page }) => {
  await rundgangStarten(page, "en");
  await expect(page.locator(`${POPOVER} .driver-popover-next-btn`)).toHaveText("Next");
});

test("auf schmalen Bildschirmen klappt die Leiste für die Werkzeuge weg", async ({ page }) => {
  // Below 1024px the open sidebar covers the whole page, so a station on a tool
  // would point at something nobody can see.
  await page.setViewportSize({ width: 900, height: 800 });
  await rundgangStarten(page);
  await stationErwarten(page, "tools-sidebar");
  await expect(page.locator('[data-tour="tools-sidebar"]')).toHaveClass(/w-full/);

  await weiterKlicken(page);
  await stationErwarten(page, "tool-translation");
  await expect(page.locator('[data-tour="tools-sidebar"]')).toHaveClass(/w-20/);
});

test("ein fehlender Anker bricht den Rundgang nicht", async ({ page }) => {
  // A tool can hide its entry, the screencast does while it resumes a running job.
  await rundgangStarten(page);
  await stationErwarten(page, "tools-sidebar");
  await page.evaluate(() =>
    document.querySelector('[data-tour="tool-translation"]')?.removeAttribute("data-tour"),
  );

  await weiterKlicken(page);
  await expect(page.locator(`${POPOVER} .driver-popover-progress-text`)).toHaveText(
    "Schritt 2 von 9",
    { timeout: 8_000 },
  );
});

test.describe("Einladung auf der Startseite", () => {
  const KARTE = '[data-tour="tools-tour-invite"]';

  /** Puts the mark back, otherwise the first run would take the invitation away for good. */
  test.beforeEach(async ({ page }) => {
    await page.request.post("/api/me/tools-tour-seen", { data: { seen: false } });
  });

  test.afterEach(async ({ page }) => {
    await page.request.post("/api/me/tools-tour-seen", { data: { seen: false } });
  });

  test("führt in den Rundgang", async ({ page }) => {
    await page.goto("/de", { waitUntil: "domcontentloaded" });
    await willkommenSchliessen(page);
    await expect(page.locator(KARTE)).toBeVisible({ timeout: 20_000 });
    await page.locator(KARTE).getByRole("button", { name: "Starten", exact: true }).click();
    await stationErwarten(page, "tools-sidebar");
  });

  test("ein Abbruch mittendrin lässt sie stehen", async ({ page }) => {
    await page.goto("/de", { waitUntil: "domcontentloaded" });
    await willkommenSchliessen(page);
    await page.locator(KARTE).getByRole("button", { name: "Starten", exact: true }).click();
    await stationErwarten(page, "tools-sidebar");
    await weiterKlicken(page);
    await stationErwarten(page, "tool-translation");
    await page.keyboard.press("Escape");
    await expect(page.locator(POPOVER)).toHaveCount(0);

    expect((await (await page.request.get("/api/me")).json()).tools_tour_seen_at).toBeNull();
    await page.goto("/de", { waitUntil: "domcontentloaded" });
    await willkommenSchliessen(page);
    await expect(page.locator(KARTE)).toBeVisible({ timeout: 20_000 });
  });

  test("\"Ausblenden\" nimmt sie weg", async ({ page }) => {
    await page.goto("/de", { waitUntil: "domcontentloaded" });
    await willkommenSchliessen(page);
    await page.locator(KARTE).getByRole("button", { name: "Ausblenden" }).click();
    await expect(page.locator(KARTE)).toHaveCount(0);

    await page.goto("/de", { waitUntil: "domcontentloaded" });
    await willkommenSchliessen(page);
    await expect(page.locator(KARTE)).toHaveCount(0);
  });

  test("die letzte Station nimmt sie weg", async ({ page }) => {
    await page.goto("/de", { waitUntil: "domcontentloaded" });
    await willkommenSchliessen(page);
    await page.locator(KARTE).getByRole("button", { name: "Starten", exact: true }).click();
    await stationErwarten(page, "tools-sidebar");
    for (const station of STATIONEN.slice(1)) {
      await weiterKlicken(page);
      await stationErwarten(page, station.anker);
    }
    await page.waitForTimeout(700);
    await page.locator(".driver-popover-next-btn").click();
    await expect(page.locator(POPOVER)).toHaveCount(0);

    await page.goto("/de", { waitUntil: "domcontentloaded" });
    await willkommenSchliessen(page);
    await expect(page.locator(KARTE)).toHaveCount(0);
  });
});

import { test, expect, type Page } from "@playwright/test";

/**
 * Zielsprache der Auswahlleisten-Übersetzung: Sichtprüfung am laufenden System.
 *
 * Prüft, dass das neue Auswahlfeld im Einstellungen-Dialog steht, dass eine
 * Änderung gespeichert wird und dass die Aktionen der Auswahlleiste danach mit
 * dem neuen Sprachcode nachgeladen werden.
 *
 * Das Auswahlfeld ist kein natives <select>, sondern die eigene Select-Komponente
 * (Knopf mit role=combobox, Liste im Portal mit role=option).
 */
const WORKSPACE = process.env.E2E_WORKSPACE ?? "1ea7b2fa-b237-4bbd-801b-c9793d388984";
const TITLE = "Zielsprache beim Übersetzen im Dokument";

/** Der Knopf des Auswahlfeldes, das direkt unter der neuen Überschrift steht. */
function langCombobox(page: Page) {
  return page
    .locator("div")
    .filter({ has: page.getByText(TITLE, { exact: true }) })
    .last()
    .getByRole("combobox");
}

async function openSettings(page: Page) {
  await page.getByRole("button", { name: /Einstellungen|Settings/i }).first().click();
  await expect(page.getByText(TITLE, { exact: true })).toBeVisible();
}

test("Zielsprache waehlen, speichern, Aktionen laden neu", async ({ page }) => {
  const popupCalls: string[] = [];
  const patchBodies: string[] = [];
  page.on("request", (req) => {
    const url = req.url();
    if (url.includes("/popup-actions")) popupCalls.push(url);
    if (req.method() === "PATCH" && url.includes("/settings")) patchBodies.push(req.postData() ?? "");
  });

  await page.goto(`/de/workspace/${WORKSPACE}`, { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(4000);

  await openSettings(page);
  const combo = langCombobox(page);
  await expect(combo).toHaveText(/Englisch|English/);
  await page.screenshot({ path: "e2e/screens/popup-lang-dialog.png" });

  popupCalls.length = 0;
  patchBodies.length = 0;

  await combo.click();
  await page.getByRole("option", { name: /^(Türkisch|Turkish)$/ }).click();
  await expect(combo).toHaveText(/Türkisch|Turkish/);
  await page.waitForTimeout(2500);

  expect(patchBodies.join("|")).toContain('"popup_translate_lang":"tr"');
  expect(popupCalls.join("|")).toContain("target=tr");
  await page.screenshot({ path: "e2e/screens/popup-lang-turkish.png" });

  // Neu laden: die Wahl steht noch da
  await page.reload({ waitUntil: "domcontentloaded" });
  await page.waitForTimeout(4000);
  await openSettings(page);
  await expect(langCombobox(page)).toHaveText(/Türkisch|Turkish/);

  // Zuruecksetzen, damit der Teststand sauber bleibt
  await langCombobox(page).click();
  await page.getByRole("option", { name: /^(Englisch|English)$/ }).click();
  await page.waitForTimeout(1500);
});

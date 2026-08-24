import path from "node:path";

import { expect, test } from "@playwright/test";

/** Die Sprache muss im Schritt Einstellungen sichtbar und aenderbar sein. */
test("Einstellungen zeigen die Sprache mit nur DE und EN", async ({ page }) => {
  test.setTimeout(180_000);
  await page.goto("/de/tools/screencast", { waitUntil: "domcontentloaded" });

  await page.getByText("Präsentation bereits übersetzt", { exact: false }).click();
  await page.setInputFiles('input[type="file"]', path.join(__dirname, "mini.pptx"));
  await page.getByRole("button", { name: /Weiter/i }).click();

  // Schritt Anweisung: ohne Zusatz weiter zu den Skripten
  const weiter = page.getByRole("button", { name: /Skripte erzeugen|Weiter/i }).first();
  await expect(weiter).toBeEnabled({ timeout: 60_000 });
  await weiter.click();

  // Schritt Skripte: weiter zu den Einstellungen
  const zuEinstellungen = page.getByRole("button", { name: /Alle Skripte übernehmen/i });
  await expect(zuEinstellungen).toBeEnabled({ timeout: 120_000 });
  await zuEinstellungen.click();

  const feld = page.getByText("Sprache der Vertonung", { exact: false }).first();
  await expect(feld).toBeVisible({ timeout: 60_000 });

  await page.locator("#sc-lang-select").click();
  const optionen = page.locator('[role="option"]');
  await expect(optionen.first()).toBeVisible({ timeout: 10_000 });
  await page.screenshot({ path: "e2e/screens/screencast-sprache-einstellungen.png" });

  expect(await optionen.allInnerTexts()).toEqual(["Deutsch", "Englisch"]);
});

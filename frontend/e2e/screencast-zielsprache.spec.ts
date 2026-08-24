import { expect, test } from "@playwright/test";

/** Der Screencast darf nur DE und EN als Zielsprache anbieten. */
test("Zielsprache bietet nur Deutsch und Englisch", async ({ page }) => {
  await page.goto("/de/tools/screencast", { waitUntil: "domcontentloaded" });

  const feld = page.getByText("Zielsprache", { exact: false }).first();
  await expect(feld).toBeVisible({ timeout: 30_000 });

  const auswahl = page.locator('[role="combobox"]').first();
  await auswahl.click();

  const optionen = page.locator('[role="option"]');
  await expect(optionen.first()).toBeVisible({ timeout: 10_000 });
  await page.screenshot({ path: "e2e/screens/screencast-zielsprache.png" });

  expect(await optionen.allInnerTexts()).toEqual(["Deutsch", "Englisch"]);
});

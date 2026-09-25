import path from "node:path";

import { expect, test } from "@playwright/test";

/** The language is chosen once at the start, step 6 no longer asks and still voices in it. */
test("Sprache nur am Anfang, Einstellungen übernehmen sie", async ({ page }) => {
  test.setTimeout(180_000);
  let jobUuid = "";
  const gespeichert: string[] = [];
  page.on("request", (r) => {
    const treffer = r.url().match(/\/api\/screencast\/([0-9a-f]{32})\/einstellungen$/);
    if (treffer && r.method() === "PUT") {
      jobUuid = treffer[1];
      gespeichert.push(r.postDataJSON().target_lang);
    }
  });

  try {
    await page.goto("/de/tools/screencast", { waitUntil: "domcontentloaded" });
    await page.getByText("Datei hierher ziehen oder").waitFor({ timeout: 30_000 });
    await page.setInputFiles('input[type="file"][accept=".pptx"]', path.join(__dirname, "mini.pptx"));
    await page.getByText("Übersetzung überspringen").click();

    await page.getByRole("combobox").first().click();
    const optionen = page.locator('[role="option"]');
    await expect(optionen.first()).toBeVisible({ timeout: 10_000 });
    expect(await optionen.allInnerTexts()).toEqual(["Deutsch", "Englisch"]);
    await optionen.filter({ hasText: "Deutsch" }).click();
    await page.getByRole("button", { name: "Weiter" }).click();

    await expect(page.getByText("Wie sollen die Skripte erstellt werden?")).toBeVisible({ timeout: 120_000 });
    await page.getByRole("radio").nth(1).check();
    await page.getByRole("button", { name: "Weiter" }).click();
    await page.getByRole("button", { name: "Alle Skripte übernehmen" }).click();

    await expect(page.getByText("Geschwindigkeit", { exact: false }).first()).toBeVisible({ timeout: 30_000 });
    await expect(page.getByText("Sprache der Vertonung")).toHaveCount(0);
    await expect(page.locator("#sc-lang-select")).toHaveCount(0);
    await expect.poll(() => gespeichert.at(-1), { timeout: 10_000 }).toBe("DE");
  } finally {
    if (jobUuid) await page.request.delete(`/api/jobs/${jobUuid}`);
  }
});

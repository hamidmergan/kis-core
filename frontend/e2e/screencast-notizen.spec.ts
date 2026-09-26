import path from "node:path";

import { expect, test, type Page } from "@playwright/test";

/** Uploads a deck without translation and returns at the step that decides how scripts come about. */
async function bisAnweisungen(page: Page, datei: string, jobs: string[]) {
  page.on("response", async (r) => {
    if (r.url().endsWith("/api/screencast/upload-corrected") && r.ok()) {
      jobs.push((await r.json()).translate_job_uuid);
    }
  });
  await page.goto("/de/tools/screencast", { waitUntil: "domcontentloaded" });
  await page.getByText("Datei hierher ziehen oder").waitFor({ timeout: 30_000 });
  await page.setInputFiles('input[type="file"][accept=".pptx"]', path.join(__dirname, datei));
  await page.getByText("Übersetzung überspringen").click();
  await page.getByRole("button", { name: "Weiter" }).click();
  await expect(page.getByText("Wie sollen die Skripte erstellt werden?")).toBeVisible({ timeout: 120_000 });
}

test.describe("Skripte aus den Sprechernotizen", () => {
  const jobs: string[] = [];

  test.afterEach(async ({ page }) => {
    for (const uuid of jobs.splice(0)) await page.request.delete(`/api/jobs/${uuid}`);
  });

  test("Notizen werden zu den Sprechtexten", async ({ page }) => {
    test.setTimeout(180_000);
    await bisAnweisungen(page, "mit-notizen.pptx", jobs);
    await page.getByRole("radio", { name: /Aus den Sprechernotizen/ }).check();
    await expect(page.getByText("Zusätzliches Material (optional)")).toHaveCount(0);
    await page.getByRole("button", { name: "Weiter" }).click();

    const zeilen = page.locator("li.folien-zeile");
    await expect(zeilen).toHaveCount(2, { timeout: 30_000 });
    await expect(zeilen.first()).toContainText("Welcome to media psychology.");
    await zeilen.nth(1).locator("button").first().click();
    await expect(zeilen.nth(1)).toContainText("Keep this number in mind.");
  });

  test("Ohne Notizen gibt es einen Hinweis statt leerer Skripte", async ({ page }) => {
    test.setTimeout(180_000);
    await bisAnweisungen(page, "mini.pptx", jobs);
    await page.getByRole("radio", { name: /Aus den Sprechernotizen/ }).check();
    await page.getByRole("button", { name: "Weiter" }).click();
    await expect(page.getByText("In dieser Präsentation stehen keine Sprechernotizen.")).toBeVisible();
    await expect(page.locator("li.folien-zeile")).toHaveCount(0);
  });
});

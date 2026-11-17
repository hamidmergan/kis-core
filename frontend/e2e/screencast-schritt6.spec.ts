import path from "node:path";

import { expect, test, type Page } from "@playwright/test";

async function zuDenEinstellungen(page: Page) {
  await page.goto("/de/tools/screencast", { waitUntil: "domcontentloaded" });
  await page.getByText("Datei hierher ziehen oder").waitFor({ timeout: 30_000 });
  await page.setInputFiles('input[type="file"][accept=".pptx"]', path.join(__dirname, "mit-notizen.pptx"));
  await page.getByRole("checkbox", { name: "Übersetzung überspringen" }).check();
  await page.getByRole("combobox").first().click();
  await page.locator('[role="option"]').filter({ hasText: "Deutsch" }).click();
  await page.getByRole("button", { name: "Weiter" }).click();
  await expect(page.getByText("Wie sollen die Skripte erstellt werden?")).toBeVisible({ timeout: 120_000 });
  await page.getByRole("radio", { name: /Sprechernotizen/ }).check();
  await page.getByRole("button", { name: "Weiter" }).click();
  await page.getByRole("button", { name: "Alle Skripte übernehmen" }).click();
  await expect(page.getByText("Pause zwischen Folien", { exact: false })).toBeVisible({ timeout: 30_000 });
}

async function pauseSetzen(page: Page, wert: string) {
  await page.locator('input[type="range"]').last().evaluate((el, v) => {
    const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")!.set!;
    setter.call(el, v);
    el.dispatchEvent(new Event("input", { bubbles: true }));
  }, wert);
}

/** Step 6 keeps its settings over a reload and a step back, and a real run ends with a video. */
test("Schritt 6: Autospeichern, Neuladen, Zurück, echtes Rendern", async ({ page }) => {
  test.setTimeout(600_000);
  let jobUuid = "";
  const gespeichert: { slide_pause: number; subtitles: boolean }[] = [];
  page.on("request", (r) => {
    const treffer = r.url().match(/\/api\/screencast\/([0-9a-f]{32})\/einstellungen$/);
    if (treffer && r.method() === "PUT") {
      jobUuid = treffer[1];
      gespeichert.push(r.postDataJSON());
    }
  });

  try {
    await zuDenEinstellungen(page);
    const untertitel = page.getByRole("checkbox", { name: "Untertitel einbauen" });
    const vorher = await untertitel.isChecked();

    await pauseSetzen(page, "2.3");
    await untertitel.click();
    await expect(page.getByText("Pause zwischen Folien: 2.3s")).toBeVisible();
    await expect.poll(() => gespeichert.at(-1), { timeout: 10_000 })
      .toMatchObject({ slide_pause: 2.3, subtitles: !vorher });

    // A reload resumes the job in step 6 with the saved values.
    await page.goto(`/de/tools/screencast?resume=${jobUuid}`, { waitUntil: "domcontentloaded" });
    await expect(page.getByText("Pause zwischen Folien: 2.3s")).toBeVisible({ timeout: 60_000 });
    await expect(untertitel).toBeChecked({ checked: !vorher });

    // One step back to the scripts and forward again keeps them too.
    await page.getByRole("button", { name: "Zurück" }).last().click();
    await page.getByRole("button", { name: "Alle Skripte übernehmen" }).click();
    await expect(page.getByText("Pause zwischen Folien: 2.3s")).toBeVisible({ timeout: 30_000 });
    await expect(untertitel).toBeChecked({ checked: !vorher });

    // A real run with the configured voice provider, small enough to take a minute or two.
    await page.getByRole("button", { name: /Screencast erstellen/i }).click();
    await expect(page.getByText("Fertig!", { exact: false })).toBeVisible({ timeout: 480_000 });
    await expect(page.locator("video source")).toHaveAttribute("src", new RegExp(`/api/jobs/${jobUuid}/video`));
    const video = await page.request.get(`/api/jobs/${jobUuid}/video`);
    expect(video.status()).toBe(200);
    expect((await video.body()).length).toBeGreaterThan(10_000);
  } finally {
    if (jobUuid) await page.request.delete(`/api/jobs/${jobUuid}`);
  }
});

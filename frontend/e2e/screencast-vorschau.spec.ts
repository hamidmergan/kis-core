import path from "node:path";

import { expect, test, type Page } from "@playwright/test";

async function offeneScreencastsWegraeumen(page: Page) {
  const liste = await (await page.request.get("/api/jobs/my?limit=50")).json();
  for (const job of liste.jobs ?? []) {
    if (String(job.tool ?? "").startsWith("screencast") &&
        ["queued", "running", "awaiting_user", "pending"].includes(String(job.status))) {
      await page.request.delete(`/api/jobs/${job.job_uuid}`);
    }
  }
}

/** During rendering image, text and audio have to be visible per finished slide. */
test("Vorschau zeigt die fertigen Folien", async ({ page }) => {
  test.setTimeout(180_000);

  // The render job runs under the same UUID as the translation job.
  let jobUuid = "";
  await page.route("**/api/screencast/render", (route) => {
    jobUuid = route.request().postDataJSON().translate_job_uuid;
    return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ job_uuid: jobUuid }) });
  });

  // The progress is faked, a real run takes minutes and the voicing.
  await page.route(/\/api\/jobs\/[0-9a-f]{32}$/, (route) => {
    // Before the render job the real script generation runs, that must not be faked.
    if (!jobUuid) return route.continue();
    return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({
      job_uuid: jobUuid, status: "running",
      progress: { step: "tts", current: 1, total: 2, fertig: [0] },
    }) });
  });

  await page.route("**/api/screencast/*/vorschau/*", (route) =>
    route.fulfill({ status: 200, contentType: "audio/mpeg", body: Buffer.from("ID3") }));

  await page.goto("/de/tools/screencast", { waitUntil: "domcontentloaded" });
  await offeneScreencastsWegraeumen(page);
  await page.reload({ waitUntil: "domcontentloaded" });

  await page.getByText("Präsentation bereits übersetzt", { exact: false }).click();
  await page.setInputFiles('input[type="file"]', path.join(__dirname, "mini.pptx"));
  await page.getByRole("button", { name: /Weiter/i }).click();

  const weiter = page.getByRole("button", { name: /Skripte erzeugen|Weiter/i }).first();
  await expect(weiter).toBeEnabled({ timeout: 60_000 });
  await weiter.click();

  const zuEinstellungen = page.getByRole("button", { name: /Alle Skripte übernehmen/i });
  await expect(zuEinstellungen).toBeEnabled({ timeout: 120_000 });
  await zuEinstellungen.click();

  await page.getByRole("button", { name: /Screencast erstellen/i }).click();

  // Slide 1 is finished and clickable, slide 2 is not yet.
  const erste = page.getByRole("button", { name: /Folie 1 anhören/i });
  await expect(erste).toBeEnabled({ timeout: 60_000 });
  await expect(page.getByRole("button", { name: /Folie 2 wird noch vertont/i })).toBeDisabled();

  await erste.click();
  await expect(page.locator("audio")).toHaveAttribute("src", `/api/screencast/${jobUuid}/vorschau/0`);
  // Cancelling asks first, before the run really dies.
  await page.getByRole("button", { name: /^Abbrechen$/ }).click();
  await expect(page.getByRole("dialog")).toContainText("Rendern abbrechen?");

  await page.waitForTimeout(300);
  await page.screenshot({ path: "e2e/screens/screencast-vorschau-abbrechen.png" });

  await page.getByRole("dialog").getByRole("button", { name: /Weiter rendern/ }).click();
  await expect(page.getByRole("dialog")).toBeHidden();
  await page.waitForTimeout(300);
  await page.locator("section[aria-label]").last().screenshot({ path: "e2e/screens/screencast-vorschau.png" });

  // Only the yes in the dialog stops the run and leads back to the settings.
  await page.getByRole("button", { name: /^Abbrechen$/ }).click();
  await page.getByRole("dialog").getByRole("button", { name: /Rendern abbrechen/ }).click();
  await expect(page.getByRole("button", { name: /Screencast erstellen/i })).toBeVisible({ timeout: 30_000 });
});

/** The finished result has to be openable again later. */
test("Fertiges Ergebnis laesst sich wieder oeffnen", async ({ page }) => {
  test.setTimeout(120_000);
  const fertigUuid = "c".repeat(32);

  await page.route(`**/api/screencast/resume/${fertigUuid}`, (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({
      tool: "screencast_translate", step: "done",
      slide_texts: ["Folientext"], unchanged_slides: [], slide_images: [],
      // 24 slides so the strip overflows and the arrows have something to do.
      scripts: Array.from({ length: 24 }, (_, i) => `Folie ${i + 1} spricht.`),
      original_filename: "mini.pptx", user_prompt: "",
    }) }));

  await page.route(new RegExp(`/api/jobs/${fertigUuid}$`), (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({
      job_uuid: fertigUuid, status: "success",
      meta: { audio_id: fertigUuid, audio_count: 1, result_stem: "mini_screencast", subtitles: false },
    }) }));

  await page.goto(`/de/tools/screencast?resume=${fertigUuid}`, { waitUntil: "domcontentloaded" });

  await expect(page.getByText("Fertig!", { exact: false })).toBeVisible({ timeout: 60_000 });
  // The run stamp hangs on as a query part, otherwise the browser shows the old video.
  await expect(page.locator("video source")).toHaveAttribute("src", `/api/jobs/${fertigUuid}/video?v=mini_screencast`);

  await page.waitForTimeout(300);
  await page.screenshot({ path: "e2e/screens/screencast-ergebnis-wieder.png" });

  // Back to rendering: all slides are there now for listening again.
  await page.getByRole("button", { name: /Rendern/ }).click();
  await expect(page.getByRole("heading", { name: /Alle Folien einzeln anhören/ })).toBeVisible({ timeout: 20_000 });
  await expect(page.getByRole("button", { name: /Folie 1 anhören/i })).toBeEnabled();
  await expect(page.locator("audio")).toHaveAttribute("src", `/api/screencast/${fertigUuid}/vorschau/0`);

  // Arrows only on the desktop, and they really move the strip.
  const nachRechts = page.getByRole("button", { name: /Folien nach rechts schieben/ });
  await expect(nachRechts).toBeVisible();
  const streifen = page.locator("section[aria-label] div.overflow-x-auto");
  const vorher = await streifen.evaluate((el) => el.scrollLeft);
  await nachRechts.click();
  await expect.poll(() => streifen.evaluate((el) => el.scrollLeft)).toBeGreaterThan(vorher);
  await page.waitForTimeout(400);
  await page.screenshot({ path: "e2e/screens/screencast-rueckblick.png" });

  // Fast clicks must not select any text.
  for (const knopf of [nachRechts, page.getByRole("button", { name: /Zum fertigen Video/ }),
                       page.getByRole("button", { name: /Folie 1 anhören/i })]) {
    await expect.poll(() => knopf.evaluate((el) => getComputedStyle(el).userSelect)).toBe("none");
  }

  await page.setViewportSize({ width: 600, height: 900 });
  await expect(nachRechts).toBeHidden();
  await page.setViewportSize({ width: 1280, height: 720 });

  await page.getByRole("button", { name: /Zum fertigen Video/ }).click();
  await expect(page.getByText("Fertig!", { exact: false })).toBeVisible({ timeout: 20_000 });
});

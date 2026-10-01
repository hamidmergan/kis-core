import { expect, test } from "@playwright/test";

/** The demo runs through every real step, own files stay locked and the result is the sample video. */
test("Demo läuft alle Schritte durch", async ({ page }) => {
  test.setTimeout(120_000);
  await page.goto("/de/tools/screencast-demo", { waitUntil: "domcontentloaded" });

  // Step 1: the file is given, settings can still be changed.
  await expect(page.getByText("Beispiel-Foliensatz.pptx")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText("In der Demo ist der Foliensatz vorgegeben.")).toBeVisible();
  await expect(page.locator('input[type="file"][accept=".pptx"]')).toBeDisabled();
  await page.getByText("Übersetzung überspringen").click();
  await expect(page.getByText("Sprache der Sprechtexte")).toBeVisible();
  await page.getByText("Übersetzung überspringen").click();
  await page.getByRole("button", { name: "Weiter" }).click();

  // Step 3: slides from the prepared run, no upload of an own file.
  const vorschaubilder = page.getByRole("button", { name: /^Folie \d+ vergrößern/ });
  await expect(vorschaubilder.first()).toBeVisible({ timeout: 15_000 });
  const anzahl = await vorschaubilder.count();
  expect(anzahl).toBeGreaterThan(1);
  await expect(page.locator('input[type="file"][accept=".pptx"]')).toBeDisabled();
  await expect(page.getByText("In der Demo lassen sich keine eigenen Dateien hochladen.")).toBeVisible();
  const pptx = page.waitForEvent("download");
  await page.getByRole("button", { name: "PPTX", exact: true }).click();
  expect((await pptx).suggestedFilename()).toBe("screencast_demo.pptx");
  await page.getByRole("button", { name: "Übersetzung übernehmen und weiter" }).click();

  // Step 4: the import can be chosen but offers no file field.
  await page.getByRole("radio").nth(2).check();
  await expect(page.getByText("In der Demo lassen sich keine eigenen Dateien hochladen.")).toBeVisible();
  await expect(page.locator('input[type="file"][accept=".json"]')).toHaveCount(0);
  await page.getByRole("radio").first().check();
  await page.getByRole("button", { name: "Weiter" }).click();

  // Step 5: prepared scripts, editing works locally.
  const ersteZeile = page.locator("li.folien-zeile").first();
  await expect(ersteZeile).toBeVisible({ timeout: 15_000 });
  await expect(page.locator("li.folien-zeile")).toHaveCount(anzahl);
  await ersteZeile.getByRole("button", { name: "Skript für Folie 1 bearbeiten" }).click();
  await ersteZeile.locator("textarea").fill("Mein eigener Sprechtext zum Ausprobieren.");
  await ersteZeile.getByRole("button", { name: "Speichern" }).click();
  await expect(ersteZeile.getByText("Mein eigener Sprechtext zum Ausprobieren.")).toBeVisible();
  await page.getByRole("button", { name: "Alle Skripte übernehmen" }).click();

  // Step 6: take slide 2 out, the preview shows it as excluded.
  await expect(page.getByRole("button", { name: "Ändern" })).toBeVisible();
  await page.getByRole("button", { name: "Ändern" }).click();
  await page.getByLabel("Folie 2 in den Screencast").uncheck();
  await page.getByRole("button", { name: "Screencast erstellen" }).click();

  await expect(page.getByText(/von \d+ Folien vertont/)).toBeVisible({ timeout: 10_000 });
  await expect(page.getByRole("button", { name: "Folie 2 ist nicht im Screencast" })).toBeVisible();

  // Done: the sample video, playable with seeking and downloadable.
  const video = page.locator("video source");
  await expect(video).toHaveAttribute("src", "/api/screencast-demo/video", { timeout: 30_000 });
  const teil = await page.request.get("/api/screencast-demo/video", { headers: { Range: "bytes=0-99" } });
  expect(teil.status()).toBe(206);
  await expect(page.getByRole("button", { name: "Alles herunterladen (ZIP)" })).toBeVisible();

  const ton = await page.request.get("/api/screencast-demo/vorschau/0");
  expect(ton.status()).toBe(200);
  expect(ton.headers()["content-type"]).toBe("audio/mpeg");

  await page.getByRole("button", { name: "Demo beenden" }).click();
  await page.waitForURL(/\/tools\/screencast$/);
});

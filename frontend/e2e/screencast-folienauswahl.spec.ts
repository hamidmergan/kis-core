import path from "node:path";

import { expect, test, type Page } from "@playwright/test";

/** Slide selection in a real browser, every case clears its job away again. */
test.describe("Folienauswahl in Schritt 6", () => {
  let jobUuid = "";

  test.afterEach(async ({ page }) => {
    if (!jobUuid) return;
    await page.request.delete(`/api/jobs/${jobUuid}`);
    jobUuid = "";
  });

  /** Brings a fresh job up to the opened block in step 6. */
  async function bisSchritt6Offen(page: Page): Promise<string> {
    test.setTimeout(180_000);
    await page.goto("/de/tools/screencast", { waitUntil: "domcontentloaded" });

    await page.getByText("Präsentation bereits übersetzt", { exact: false }).click();
    await page.setInputFiles('input[type="file"]', path.join(__dirname, "mini.pptx"));

    const hochgeladen = page.waitForResponse(
      (r) => r.url().includes("/api/screencast/upload-corrected") && r.request().method() === "POST",
      { timeout: 60_000 },
    );
    await page.getByRole("button", { name: /Weiter/i }).click();
    const daten = await (await hochgeladen).json();
    jobUuid = daten.translate_job_uuid as string;

    const weiter = page.getByRole("button", { name: /Skripte erzeugen|Weiter/i }).first();
    await expect(weiter).toBeEnabled({ timeout: 60_000 });
    await weiter.click();

    const zuEinstellungen = page.getByRole("button", { name: /Alle Skripte übernehmen/i });
    await expect(zuEinstellungen).toBeEnabled({ timeout: 120_000 });
    await zuEinstellungen.click();

    const aendern = page.getByRole("button", { name: "Ändern" });
    await expect(aendern).toBeVisible({ timeout: 60_000 });
    await aendern.click();

    return jobUuid;
  }

  test("die Zusammenfassung zaehlt die Haken mit", async ({ page }) => {
    await bisSchritt6Offen(page);

    const zusammenfassung = page.getByText(/ von \d+ Folien im Screencast/);
    await expect(zusammenfassung).toBeVisible();
    const vorher = Number((await zusammenfassung.innerText()).match(/^(\d+)/)?.[1]);

    await page.getByRole("checkbox", { name: "Folie 1 in den Screencast" }).click();

    await expect(zusammenfassung).toContainText(`${vorher - 1} von`);
  });

  test("ohne Folie sperrt der Startknopf", async ({ page }) => {
    await bisSchritt6Offen(page);

    await page.getByRole("button", { name: "Keine" }).click();

    await expect(page.getByRole("button", { name: "Screencast erstellen" })).toBeDisabled();
    await expect(page.getByText("Es ist keine Folie ausgewählt.")).toBeVisible();
  });

  test("die Auswahl steht nach dem Neuladen noch", async ({ page }) => {
    const uuid = await bisSchritt6Offen(page);

    const zweiteFolie = page.getByRole("checkbox", { name: "Folie 2 in den Screencast" });
    await expect(zweiteFolie).toHaveAttribute("aria-checked", "true");

    const gespeichert = page.waitForResponse(
      (r) => r.url().includes("/einstellungen") && r.request().method() === "PUT",
    );
    await zweiteFolie.click();
    await expect(zweiteFolie).toHaveAttribute("aria-checked", "false");
    await gespeichert;

    await page.goto(`/de/tools/screencast?resume=${uuid}`, { waitUntil: "domcontentloaded" });

    const aendern = page.getByRole("button", { name: "Ändern" });
    await expect(aendern).toBeVisible({ timeout: 30_000 });
    await aendern.click();

    await expect(page.getByRole("checkbox", { name: "Folie 2 in den Screencast" }))
      .toHaveAttribute("aria-checked", "false");

    await page.waitForTimeout(300);
    await page.locator('section[aria-label="Folien"]').screenshot({
      path: "e2e/screens/screencast-folienauswahl.png",
    });
  });

  test("eine Folie ohne Ton wird nach dem Wiederhinzufuegen nicht von allein angehakt", async ({ page }) => {
    const uuid = await bisSchritt6Offen(page);

    // Faked, because a real second render pass would take too long here.
    await page.route("**/vertonungs-stand", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ einstellungen: null, stand: null, hat_ton: [true, false] }),
      }),
    );
    await page.goto(`/de/tools/screencast?resume=${uuid}`, { waitUntil: "domcontentloaded" });

    const aendern = page.getByRole("button", { name: "Ändern" });
    await expect(aendern).toBeVisible({ timeout: 30_000 });
    await aendern.click();

    const imScreencast = page.getByRole("checkbox", { name: "Folie 2 in den Screencast" });
    const neuSprechen = page.getByRole("checkbox", { name: "Folie 2 neu sprechen" });

    // Slide 2 has a script and no audio, nothing gets ticked automatically for that.
    await expect(neuSprechen).toHaveAttribute("aria-checked", "false");
    await expect(neuSprechen).toBeEnabled();

    await imScreencast.click();
    await imScreencast.click();

    await expect(imScreencast).toHaveAttribute("aria-checked", "true");
    await expect(neuSprechen).toHaveAttribute("aria-checked", "false");
  });

  test("beim erneuten Betreten von Schritt 6 wird der Stand neu geholt", async ({ page }) => {
    let holungen = 0;
    await page.route("**/vertonungs-stand", async (route) => {
      holungen += 1;
      await route.continue();
    });
    await bisSchritt6Offen(page);
    const nachDemErsten = holungen;

    await page.getByRole("button", { name: /Zurück/i }).first().click();
    await page.getByRole("button", { name: /Alle Skripte übernehmen/i }).click();
    await expect(page.getByRole("button", { name: /Ändern|Zuklappen/i })).toBeVisible({ timeout: 30_000 });

    expect(holungen).toBeGreaterThan(nachDemErsten);
  });
});

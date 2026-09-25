import path from "node:path";

import { expect, test } from "@playwright/test";

const STOFF = Buffer.from(
  "The 2016 study was led by Dr. Karla Brenner and included 1,240 participants from 14 countries.",
);

/** Extra material is measured while picking, stored before the scripts and shown again on return. */
test("Zusatzmaterial für die Skripte", async ({ page }) => {
  test.setTimeout(240_000);
  let jobUuid = "";
  const materialAufrufe: string[] = [];
  page.on("request", (r) => {
    if (/\/api\/screencast\/[0-9a-f]{32}\/material$/.test(r.url()) && r.method() !== "GET") {
      materialAufrufe.push(r.method());
    }
  });
  // The model is not asked, the scripts come back at once.
  await page.route("**/api/screencast/generate-scripts", async (route) => {
    const body = route.request().postDataJSON();
    jobUuid = body.translate_job_uuid;
    expect(materialAufrufe).toContain("POST");
    await route.fulfill({ contentType: "application/json",
      body: JSON.stringify({ scripts: body.slide_texts.map((_: string, i: number) => `Skript ${i + 1}`) }) });
  });

  try {
    await page.goto("/de/tools/screencast", { waitUntil: "domcontentloaded" });
    await page.getByText("Datei hierher ziehen oder").waitFor({ timeout: 30_000 });
    await page.setInputFiles('input[type="file"][accept=".pptx"]', path.join(__dirname, "mini.pptx"));
    await page.getByText("Übersetzung überspringen").click();
    await page.getByRole("button", { name: "Weiter" }).click();

    await expect(page.getByText("Zusätzliches Material (optional)")).toBeVisible({ timeout: 180_000 });
    await page.setInputFiles('input[type="file"][accept=".pdf,.docx,.pptx,.txt,.md"]',
      { name: "studie.txt", mimeType: "text/plain", buffer: STOFF });
    await expect(page.getByText(`${STOFF.length} Zeichen`).first()).toBeVisible({ timeout: 20_000 });

    // Manual scripts do not read any material, the block disappears.
    await page.getByRole("radio").nth(1).check();
    await expect(page.getByText("Zusätzliches Material (optional)")).toHaveCount(0);
    await page.getByRole("radio").first().check();

    await page.getByRole("button", { name: "Weiter" }).click();
    await expect(page.locator("li.folien-zeile").first()).toBeVisible({ timeout: 30_000 });
    const hinterlegt = await (await page.request.get(`/api/screencast/${jobUuid}/material`)).json();
    expect(hinterlegt.files).toEqual(["studie.txt"]);

    // Back in step 4 the stored material is named and can be removed.
    await page.getByRole("button", { name: "Zurück" }).click();
    await expect(page.getByText("Hinterlegt: studie.txt")).toBeVisible();
    await page.getByRole("button", { name: "Entfernen" }).click();
    await page.getByRole("button", { name: "Weiter" }).click();
    await expect(page.locator("li.folien-zeile").first()).toBeVisible({ timeout: 30_000 });
    expect(materialAufrufe).toEqual(["POST", "DELETE"]);
    expect((await (await page.request.get(`/api/screencast/${jobUuid}/material`)).json()).files).toEqual([]);
  } finally {
    if (jobUuid) await page.request.delete(`/api/jobs/${jobUuid}`);
  }
});

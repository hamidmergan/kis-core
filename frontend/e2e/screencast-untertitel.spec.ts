import path from "node:path";

import { expect, test } from "@playwright/test";

/** The checkbox in the settings has to send the subtitle choice along. */
test("Einstellungen haben einen Haken fuer Untertitel", async ({ page }) => {
  test.setTimeout(180_000);

  let gesendet: Record<string, unknown> | null = null;
  // The job is intercepted, otherwise a real render would start.
  await page.route("**/api/screencast/render", async (route) => {
    gesendet = route.request().postDataJSON();
    await route.fulfill({ status: 409, contentType: "application/json", body: JSON.stringify({ detail: "Test" }) });
  });

  await page.goto("/de/tools/screencast", { waitUntil: "domcontentloaded" });

  // An open screencast blocks the upload step, so clean up first.
  const liste = await (await page.request.get("/api/jobs/my?limit=50")).json();
  for (const job of liste.jobs ?? []) {
    if (String(job.tool ?? "").startsWith("screencast") &&
        ["queued", "running", "awaiting_user", "pending"].includes(String(job.status))) {
      await page.request.delete(`/api/jobs/${job.job_uuid}`);
    }
  }
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

  const haken = page.getByRole("checkbox", { name: "Untertitel einbauen" });
  await expect(haken).toBeVisible({ timeout: 60_000 });
  await expect(haken).toHaveAttribute("aria-checked", "false");

  await haken.click();
  await expect(haken).toHaveAttribute("aria-checked", "true");
  await page.waitForTimeout(300);
  await haken.locator("..").screenshot({ path: "e2e/screens/screencast-untertitel.png" });

  await page.getByRole("button", { name: /Screencast erstellen/i }).click();
  await expect.poll(() => gesendet).not.toBeNull();
  expect(gesendet!.subtitles).toBe(true);
});

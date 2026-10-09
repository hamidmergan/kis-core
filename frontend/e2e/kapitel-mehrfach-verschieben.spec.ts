import { test, expect, request as playwrightRequest, type Page } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

/** Checked files move into a chapter together, unchecked ones stay where they are. */

const OWNER = { username: process.env.E2E_USER ?? "a", password: process.env.E2E_PASS ?? "a" };
const TITEL = "E2E Kapitel mehrfach verschieben";
const KAPITEL = "Woche 1";
// Real PDFs, only a file that is read in completely can be checked.
const PDF_DIR = process.env.E2E_PDF_DIR ?? path.join(__dirname, "../../private/demo-material");
const DATEIEN = ["DEMO_Semesterplan_WS_2026_27.pdf", "DEMO_Uebungsblatt_1_mit_Loesungen.pdf", "DEMO_Fallstudie_Neubau_Mensa.pdf"];
// Screenshots stay out of the project, the runner passes the scratchpad.
const SHOTS = process.env.SHOTS_DIR ?? "/tmp";

test.use({ storageState: { cookies: [], origins: [] }, locale: "de-DE" });
test.setTimeout(300_000);

/** Logs in and clears the welcome dialog, which a fresh profile always gets. */
async function anmelden(page: Page) {
  await page.goto("/login", { waitUntil: "domcontentloaded" });
  await page.waitForSelector("#username");
  await page.fill("#username", OWNER.username);
  await page.fill("#password", OWNER.password);
  await page.locator('button[type="submit"]').click();
  await page.waitForURL((url) => !url.pathname.includes("login"), { timeout: 30_000 });
  const dialog = page.locator("[role=dialog]");
  if (await dialog.count()) {
    await dialog.locator("button[aria-label]").first().click();
    await expect(dialog).toHaveCount(0);
  }
}

test("Angehakte Dateien gemeinsam in ein Kapitel verschieben", async ({ page, baseURL }) => {
  test.skip(!fs.existsSync(path.join(PDF_DIR, DATEIEN[0])), "Demo-PDFs fehlen");
  const owner = await playwrightRequest.newContext({ baseURL });
  expect((await owner.post("/auth/login", { data: OWNER })).ok()).toBeTruthy();
  const angelegt = await (await owner.post("/api/ai-assistant/workspaces", { form: { title: TITEL } })).json();
  const base = `/api/ai-assistant/workspaces/${angelegt.uuid}`;
  const kapitel = await (await owner.post(`${base}/chapters`, { data: { name: KAPITEL } })).json();
  type Quelle = { filename: string; status: string; chapter_uuid: string | null; progress?: unknown };
  const quellen = async () => (await (await owner.get(base)).json()).sources as Quelle[];

  try {
    for (const name of DATEIEN) {
      const res = await owner.post(`${base}/sources`, {
        multipart: { file: { name, mimeType: "application/pdf", buffer: fs.readFileSync(path.join(PDF_DIR, name)) } },
      });
      expect(res.ok()).toBeTruthy();
    }
    await expect.poll(async () => (await quellen()).filter((s) => s.status === "ready" && !s.progress).length, {
      timeout: 240_000, intervals: [3000],
    }).toBe(DATEIEN.length);

    await anmelden(page);
    await page.goto(`/de/workspace/${angelegt.uuid}`, { waitUntil: "domcontentloaded" });
    const zeile = (name: string) => page.locator('[data-tour="source-row"]', { hasText: name });
    const haken = (name: string) => zeile(name).locator('[data-tour="source-check"]');
    const leiste = page.locator(".sources-select-all");
    const knopf = page.getByTestId("move-checked");
    await expect(zeile(DATEIEN[0])).toBeVisible({ timeout: 30_000 });

    // Chat selection: everything checked, still no move button, only the pencil.
    if (!(await leiste.getByRole("button", { name: "Alle abwählen" }).count())) await leiste.click();
    await expect(knopf).toHaveCount(0);
    await expect(page.getByTestId("move-mode")).toBeVisible();
    await page.screenshot({ path: path.join(SHOTS, "mehrfach-00-normal.png") });

    // The pencil starts the mode with nothing checked and the count at zero.
    await page.getByTestId("move-mode").click();
    await expect(page.getByTestId("move-bar")).toContainText("Auswählen");
    await expect(knopf).toContainText("Verschieben (0)");
    await expect(knopf).toBeDisabled();
    for (const n of DATEIEN) await expect(haken(n)).toHaveAttribute("aria-label", "Material auswählen");
    await haken(DATEIEN[0]).click();
    await haken(DATEIEN[1]).click();
    await expect(knopf).toContainText("Verschieben (2)");
    await knopf.click();
    await page.waitForTimeout(300);
    await page.screenshot({ path: path.join(SHOTS, "mehrfach-01-menue.png") });
    await leiste.getByRole("button", { name: KAPITEL }).click();

    await expect.poll(async () => {
      const q = await quellen();
      return DATEIEN.map((n) => q.find((s) => s.filename === n)?.chapter_uuid ?? null);
    }).toEqual([kapitel.uuid, kapitel.uuid, null]);

    // The mode is over and the chat selection is back untouched.
    await expect(page.getByTestId("move-bar")).toHaveCount(0);
    for (const n of DATEIEN) await expect(haken(n)).toHaveAttribute("aria-label", "Material abwählen");
    await page.waitForTimeout(500);
    await page.screenshot({ path: path.join(SHOTS, "mehrfach-02-verschoben.png") });

    // Cancel leaves everything where it is.
    await page.getByTestId("move-mode").click();
    await haken(DATEIEN[2]).click();
    await page.getByTestId("move-cancel").click();
    await expect(page.getByTestId("move-bar")).toHaveCount(0);
    expect((await quellen()).find((s) => s.filename === DATEIEN[2])?.chapter_uuid ?? null).toBeNull();
  } finally {
    await owner.delete(base);
  }
});

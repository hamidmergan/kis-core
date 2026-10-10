import { test, expect, request as playwrightRequest, type Page } from "@playwright/test";
import path from "node:path";

/** The pen orders chapters and files with arrows, the order survives a reload. */

const OWNER = { username: process.env.E2E_USER ?? "a", password: process.env.E2E_PASS ?? "a" };
const TITEL = "E2E Reihenfolge ordnen";
const KAPITEL = ["Woche 1", "Woche 2"];
// Texts need no reading in, the newest one comes first.
const TEXTE = ["Text A", "Text B", "Text C"];
// Screenshots stay out of the project, the runner passes the scratchpad.
const SHOTS = process.env.SHOTS_DIR ?? "/tmp";

test.use({ storageState: { cookies: [], origins: [] }, locale: "de-DE" });
test.setTimeout(180_000);

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

test("Kapitel und Materialien über den Stift ordnen", async ({ page, baseURL }) => {
  const owner = await playwrightRequest.newContext({ baseURL });
  expect((await owner.post("/auth/login", { data: OWNER })).ok()).toBeTruthy();
  const angelegt = await (await owner.post("/api/ai-assistant/workspaces", { form: { title: TITEL } })).json();
  const base = `/api/ai-assistant/workspaces/${angelegt.uuid}`;
  type Quelle = { filename: string; uuid: string };
  type Kapitel = { name: string };
  const stand = async () => (await (await owner.get(base)).json()) as { sources: Quelle[]; chapters: Kapitel[] };

  try {
    for (const titel of TEXTE) {
      const res = await owner.post(`${base}/sources/text`, { data: { title: titel, text: `Inhalt von ${titel}.` } });
      expect(res.ok()).toBeTruthy();
    }

    await anmelden(page);
    await page.goto(`/de/workspace/${angelegt.uuid}`, { waitUntil: "domcontentloaded" });
    const zeilen = page.locator('[data-tour="source-row"]');
    await expect(zeilen).toHaveCount(TEXTE.length, { timeout: 30_000 });
    await expect(zeilen.first()).toContainText("Text C");

    // Without chapters the pen orders only, nothing to pick and no move button.
    await page.getByTestId("move-mode").click();
    await expect(page.getByTestId("move-bar")).toContainText("Reihenfolge ändern");
    await expect(page.getByTestId("move-checked")).toHaveCount(0);
    await expect(zeilen.first().getByTestId("move-up")).toBeDisabled();
    await expect(zeilen.last().getByTestId("move-down")).toBeDisabled();
    await zeilen.first().getByTestId("move-down").click();
    await expect(zeilen.nth(1)).toContainText("Text C");
    await expect(zeilen.first()).toContainText("Text B");
    await page.waitForTimeout(300);
    await page.screenshot({ path: path.join(SHOTS, "ordnen-01-ohne-kapitel.png") });
    await page.getByTestId("move-cancel").click();
    await expect(zeilen.first().getByTestId("move-up")).toHaveCount(0);

    // Two chapters, the pen now shows arrows on the chapter heads too.
    for (const name of KAPITEL) {
      expect((await owner.post(`${base}/chapters`, { data: { name } })).ok()).toBeTruthy();
    }
    await page.reload({ waitUntil: "domcontentloaded" });
    await expect(zeilen).toHaveCount(TEXTE.length, { timeout: 30_000 });
    await expect(zeilen.first()).toContainText("Text B");
    await page.getByTestId("move-mode").click();
    await expect(page.getByTestId("move-bar")).toContainText("Auswählen");
    const kopf = (name: string) => page.locator("div.select-none", { hasText: name });
    await expect(kopf(KAPITEL[0]).getByTestId("move-up")).toBeDisabled();
    await kopf(KAPITEL[1]).getByTestId("move-up").click();
    await expect.poll(async () => (await stand()).chapters.map((c) => c.name)).toEqual([KAPITEL[1], KAPITEL[0]]);
    await page.waitForTimeout(300);
    await page.screenshot({ path: path.join(SHOTS, "ordnen-02-mit-kapitel.png") });

    // The file order sticks on the server as well.
    await zeilen.last().getByTestId("move-up").click();
    await expect.poll(async () => (await stand()).sources.map((s) => s.filename.replace(/\.pdf$/, ""))).toEqual(["Text B", "Text A", "Text C"]);
    await page.reload({ waitUntil: "domcontentloaded" });
    await expect(zeilen).toHaveCount(TEXTE.length, { timeout: 30_000 });
    await expect(zeilen.nth(1)).toContainText("Text A");
  } finally {
    await owner.delete(base);
  }
});

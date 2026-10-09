import { test, expect, request as playwrightRequest, type Page } from "@playwright/test";
import path from "node:path";

/** The add dialog puts a file straight into an existing chapter, without a choice it lands outside. */

const OWNER = { username: process.env.E2E_USER ?? "a", password: process.env.E2E_PASS ?? "a" };
const TITEL = "E2E Upload in Kapitel";
const KAPITEL = "Woche 1";
// Screenshots stay out of the project, the runner passes the scratchpad.
const SHOTS = process.env.SHOTS_DIR ?? "/tmp";

test.use({ storageState: { cookies: [], origins: [] }, locale: "de-DE" });
test.setTimeout(120_000);

// The smallest PDF the upload check accepts, reading it in may fail and does not matter here.
const pdf = (name: string) => ({
  name,
  mimeType: "application/pdf",
  buffer: Buffer.from("%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n2 0 obj<</Type/Pages/Kids[]/Count 0>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n"),
});

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

test("Datei landet im gewaehlten Kapitel, ohne Wahl ausserhalb", async ({ page, baseURL }) => {
  const owner = await playwrightRequest.newContext({ baseURL });
  expect((await owner.post("/auth/login", { data: OWNER })).ok()).toBeTruthy();
  const angelegt = await (await owner.post("/api/ai-assistant/workspaces", { form: { title: TITEL } })).json();
  const kapitel = await (await owner.post(`/api/ai-assistant/workspaces/${angelegt.uuid}/chapters`, { data: { name: KAPITEL } })).json();
  const kapitelVon = async (filename: string) => {
    const ws = await (await owner.get(`/api/ai-assistant/workspaces/${angelegt.uuid}`)).json();
    return (ws.sources as { filename: string; chapter_uuid: string | null }[]).find((s) => s.filename === filename)?.chapter_uuid;
  };

  try {
    await anmelden(page);
    await page.goto(`/de/workspace/${angelegt.uuid}`, { waitUntil: "domcontentloaded" });
    const plus = page.locator('[data-tour="add-source"]');
    const dialog = page.locator("[role=dialog]");

    // Default is no chapter.
    await plus.click();
    const auswahl = dialog.getByTestId("add-material-chapter");
    await expect(auswahl).toContainText("Ohne Kapitel");
    await page.screenshot({ path: path.join(SHOTS, "kapitel-01-standard.png") });

    // Pick the chapter, then the file.
    await auswahl.locator("#add-material-chapter-select").click();
    await page.getByRole("option", { name: KAPITEL }).click();
    await expect(auswahl).toContainText(KAPITEL);
    await page.screenshot({ path: path.join(SHOTS, "kapitel-02-gewaehlt.png") });
    let chooser = page.waitForEvent("filechooser");
    await dialog.getByTestId("add-material-file").click();
    await (await chooser).setFiles(pdf("im-kapitel.pdf"));
    await expect.poll(() => kapitelVon("im-kapitel.pdf"), { timeout: 30_000 }).toBe(kapitel.uuid);

    // Opening again starts without a chapter, the file stays outside.
    await plus.click();
    await expect(auswahl).toContainText("Ohne Kapitel");
    chooser = page.waitForEvent("filechooser");
    await dialog.getByTestId("add-material-file").click();
    await (await chooser).setFiles(pdf("ohne-kapitel.pdf"));
    await expect.poll(() => kapitelVon("ohne-kapitel.pdf"), { timeout: 30_000 }).toBeNull();
    await page.screenshot({ path: path.join(SHOTS, "kapitel-03-liste.png") });
  } finally {
    await owner.delete(`/api/ai-assistant/workspaces/${angelegt.uuid}`);
  }
});

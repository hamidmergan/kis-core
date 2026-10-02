import { test, expect, request as playwrightRequest, type Page } from "@playwright/test";
import path from "node:path";

/** The plus opens one dialog for file and link, and a link becomes a PDF source. */

const OWNER = { username: process.env.E2E_USER ?? "a", password: process.env.E2E_PASS ?? "a" };
const TITEL = "E2E Webseite als Quelle";
const SEITE = "https://de.wikipedia.org/wiki/Photosynthese";
// Screenshots stay out of the project, the runner passes the scratchpad.
const SHOTS = process.env.SHOTS_DIR ?? "/tmp";

// The backend reads Accept-Language for error texts, not the /de/ URL, so the
// browser locale has to match or the blocked-address message comes back in English.
test.use({ storageState: { cookies: [], origins: [] }, locale: "de-DE" });

// Fetch, LibreOffice and the ingest all run inside this one test.
test.setTimeout(240_000);

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

test("Link einlesen: Modal, Sperre, Erfolg, Dublette, Viewer", async ({ page, baseURL }) => {
  const owner = await playwrightRequest.newContext({ baseURL });
  expect((await owner.post("/auth/login", { data: OWNER })).ok()).toBeTruthy();
  const angelegt = await (await owner.post("/api/ai-assistant/workspaces", { form: { title: TITEL } })).json();

  try {
    await anmelden(page);
    await page.goto(`/de/workspace/${angelegt.uuid}`, { waitUntil: "domcontentloaded" });
    const plus = page.locator('[data-tour="add-source"]');
    const dialog = page.locator("[role=dialog]");

    // The plus opens the dialog with both ways in.
    await plus.click();
    await expect(dialog.getByText("Material hinzufügen")).toBeVisible();
    await expect(dialog.getByTestId("add-material-file")).toBeVisible();
    await expect(dialog.getByTestId("add-material-link")).toBeVisible();
    await page.screenshot({ path: path.join(SHOTS, "link-01-modal.png") });

    // The file box opens the picker and closes the dialog.
    const chooser = page.waitForEvent("filechooser");
    await dialog.getByTestId("add-material-file").click();
    await chooser;
    await expect(dialog).toHaveCount(0);

    // An internal address is refused and the dialog stays open.
    await plus.click();
    await dialog.getByTestId("add-material-link").fill("http://10.0.0.5/");
    await dialog.getByRole("button", { name: "Einlesen" }).click();
    await expect(dialog.getByText("Diese Adresse darf nicht abgerufen werden.")).toBeVisible();
    await page.screenshot({ path: path.join(SHOTS, "link-02-sperre.png") });

    // A real page becomes a PDF source at the top of the list.
    await dialog.getByTestId("add-material-link").fill(SEITE);
    await dialog.getByRole("button", { name: "Einlesen" }).click();
    await expect(dialog).toHaveCount(0, { timeout: 90_000 });
    const panel = page.locator('[data-tour="sources-panel"]');
    const name = panel.locator("span[title]").filter({ hasText: /Photosynthese/ }).first();
    await expect(name).toBeVisible();
    await expect(name).toHaveAttribute("title", SEITE);
    await page.screenshot({ path: path.join(SHOTS, "link-03-quelle.png") });

    // The same link again is a duplicate.
    await plus.click();
    await dialog.getByTestId("add-material-link").fill(SEITE);
    await dialog.getByRole("button", { name: "Einlesen" }).click();
    await expect(dialog.getByText(/schon im/)).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(dialog).toHaveCount(0);

    // Ready within two minutes, the row turns into a button.
    const zeile = panel.locator("[role=button]").filter({ hasText: /Photosynthese/ }).first();
    await expect(zeile).toBeVisible({ timeout: 120_000 });
    const detail = await (await owner.get(`/api/ai-assistant/workspaces/${angelegt.uuid}`)).json();
    const quelle = detail.sources.find((s: { source_url?: string }) => s.source_url === SEITE);
    expect(quelle.status).toBe("ready");
    expect(quelle.filename.endsWith(".pdf")).toBeTruthy();
    expect(quelle.chunk_count).toBeGreaterThan(0);

    // The viewer shows the PDF.
    await zeile.click();
    await expect(page.locator("embedpdf-container")).toBeVisible({ timeout: 30_000 });
    await page.waitForTimeout(2_000);
    await page.screenshot({ path: path.join(SHOTS, "link-04-viewer.png") });
  } finally {
    await owner.delete(`/api/ai-assistant/workspaces/${angelegt.uuid}`);
  }
});

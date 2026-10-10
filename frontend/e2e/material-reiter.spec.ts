import { test, expect, request as playwrightRequest, type Page } from "@playwright/test";
import path from "node:path";

/** The add dialog has one tab per way in, text and a page from Pages become sources. */

const OWNER = { username: process.env.E2E_USER ?? "a", password: process.env.E2E_PASS ?? "a" };
const TITEL = "E2E Material Reiter";
// Screenshots stay out of the project, the runner passes the scratchpad.
const SHOTS = process.env.SHOTS_DIR ?? "/tmp";
const TEXT = "Die Photosynthese wandelt Lichtenergie in chemische Energie um. Dabei entstehen Zucker und Sauerstoff.";

test.use({ storageState: { cookies: [], origins: [] }, locale: "de-DE" });
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

test("Reiter: Wechsel, Rueckkehr zu Datei, Text und Pages als Quelle", async ({ page, baseURL }) => {
  const owner = await playwrightRequest.newContext({ baseURL });
  expect((await owner.post("/auth/login", { data: OWNER })).ok()).toBeTruthy();
  const pages = (await (await owner.get("/api/pages")).json()).pages.filter((p: { status: string }) => p.status === "success");
  const angelegt = await (await owner.post("/api/ai-assistant/workspaces", { form: { title: TITEL } })).json();

  try {
    await anmelden(page);
    await page.goto(`/de/workspace/${angelegt.uuid}`, { waitUntil: "domcontentloaded" });
    const plus = page.locator('[data-tour="add-source"]');
    const dialog = page.locator("[role=dialog]");
    const panel = page.locator('[data-tour="sources-panel"]');

    // Each tab shows only its own way in.
    await plus.click();
    await expect(dialog.getByTestId("add-material-file")).toBeVisible();
    await expect(dialog.getByTestId("add-material-link")).toHaveCount(0);
    await dialog.getByRole("tab", { name: "Text" }).click();
    await expect(dialog.getByTestId("add-material-file")).toHaveCount(0);
    await expect(dialog.getByTestId("add-material-text-title")).toBeVisible();

    // Closing and reopening starts on the file tab again with empty fields.
    await dialog.getByTestId("add-material-text-title").fill("Weg damit");
    await page.keyboard.press("Escape");
    await expect(dialog).toHaveCount(0);
    await plus.click();
    await expect(dialog.getByTestId("add-material-file")).toBeVisible();
    await dialog.getByRole("tab", { name: "Text" }).click();
    await expect(dialog.getByTestId("add-material-text-title")).toHaveValue("");

    // Pasted text becomes a source.
    await dialog.getByTestId("add-material-text-title").fill("Reiter Text");
    await dialog.getByTestId("add-material-text").fill(TEXT);
    await page.screenshot({ path: path.join(SHOTS, "reiter-01-text.png") });
    await dialog.getByTestId("add-material-text-submit").click();
    await expect(dialog).toHaveCount(0, { timeout: 30_000 });
    await expect(panel.getByText(/Reiter Text/).first()).toBeVisible({ timeout: 30_000 });

    // A finished page from Pages becomes a source.
    if (pages.length > 0) {
      await plus.click();
      await dialog.getByRole("tab", { name: "Pages" }).click();
      await dialog.locator("#add-material-page-select").click();
      await page.getByRole("option", { name: pages[0].title }).click();
      await page.screenshot({ path: path.join(SHOTS, "reiter-02-pages.png") });
      await dialog.getByTestId("add-material-page-submit").click();
      await expect(dialog).toHaveCount(0, { timeout: 60_000 });
      await expect(panel.getByText(pages[0].title).first()).toBeVisible({ timeout: 30_000 });
    }

    const detail = await (await owner.get(`/api/ai-assistant/workspaces/${angelegt.uuid}`)).json();
    expect(detail.sources.length).toBe(pages.length > 0 ? 2 : 1);
  } finally {
    await owner.delete(`/api/ai-assistant/workspaces/${angelegt.uuid}`);
  }
});

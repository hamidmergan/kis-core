import { test, expect, request as playwrightRequest, type Page } from "@playwright/test";
import path from "node:path";

/** A YouTube link plus a pasted transcript becomes a source, the viewer asks before it loads anything from Google. */

const OWNER = { username: process.env.E2E_USER ?? "a", password: process.env.E2E_PASS ?? "a" };
const TITEL = "E2E YouTube als Quelle";
// The first video ever uploaded to YouTube, it is not going away.
const VIDEO = "https://youtu.be/jNQXAC9IVRw";
const KANONISCH = "https://www.youtube.com/watch?v=jNQXAC9IVRw";
const TRANSKRIPT = [
  "0:00", "Alright, so here we are in front of the elephants",
  "0:05", "the cool thing about these guys is that they have really really really long trunks",
  "0:12", "and that is cool",
].join("\n");
const SHOTS = process.env.SHOTS_DIR ?? "/tmp";

test.use({ storageState: { cookies: [], origins: [] }, locale: "de-DE" });
test.setTimeout(240_000);

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

test("YouTube: Modal, Fehler, Erfolg, Zwei-Klick-Fläche, Transkript", async ({ page, baseURL }) => {
  const owner = await playwrightRequest.newContext({ baseURL });
  expect((await owner.post("/auth/login", { data: OWNER })).ok()).toBeTruthy();
  const angelegt = await (await owner.post("/api/ai-assistant/workspaces", { form: { title: TITEL } })).json();

  try {
    await anmelden(page);
    await page.goto(`/de/workspace/${angelegt.uuid}`, { waitUntil: "domcontentloaded" });
    const plus = page.locator('[data-tour="add-source"]');
    const dialog = page.locator("[role=dialog]");

    // The dialog carries the third way in, behind its own tab.
    await plus.click();
    await dialog.getByRole("tab", { name: "YouTube" }).click();
    await expect(dialog.getByTestId("add-material-youtube-link")).toBeVisible();
    await expect(dialog.getByTestId("add-material-youtube-transcript")).toBeVisible();
    await page.screenshot({ path: path.join(SHOTS, "youtube-e2e-01-modal.png") });

    // A foreign link is refused and the dialog stays open.
    await dialog.getByTestId("add-material-youtube-link").fill("https://vimeo.com/12345");
    await dialog.getByTestId("add-material-youtube-transcript").fill(TRANSKRIPT);
    await dialog.getByTestId("add-material-youtube-submit").click();
    const fehler = dialog.locator("#add-material-youtube-error");
    await expect(fehler).toHaveText("Das ist kein Link auf ein YouTube-Video.");

    // The folded guide also says "Zeitstempel", so the error is read by its id.
    await dialog.getByTestId("add-material-youtube-link").fill(VIDEO);
    await dialog.getByTestId("add-material-youtube-transcript").fill("Nur Text ohne eine Zeit");
    await dialog.getByTestId("add-material-youtube-submit").click();
    await expect(fehler).toContainText("Zeitstempel");
    await page.screenshot({ path: path.join(SHOTS, "youtube-e2e-02-fehler.png") });

    // The real thing becomes a source at the top of the list.
    await dialog.getByTestId("add-material-youtube-transcript").fill(TRANSKRIPT);
    await dialog.getByTestId("add-material-youtube-submit").click();
    await expect(dialog).toHaveCount(0, { timeout: 30_000 });
    const panel = page.locator('[data-tour="sources-panel"]');
    const zeile = panel.locator("[role=button]").filter({ hasText: /\.youtube/ }).first();
    await expect(zeile).toBeVisible({ timeout: 120_000 });
    const detail = await (await owner.get(`/api/ai-assistant/workspaces/${angelegt.uuid}`)).json();
    const quelle = detail.sources.find((s: { source_url?: string }) => s.source_url === KANONISCH);
    expect(quelle.status).toBe("ready");
    expect(quelle.filename.endsWith(".youtube")).toBeTruthy();
    expect(quelle.chunk_count).toBeGreaterThan(0);
    await page.screenshot({ path: path.join(SHOTS, "youtube-e2e-03-quelle.png") });

    // Only the host of a request counts, the app's own route path contains "youtube" too.
    const fremd: string[] = [];
    page.on("request", (r) => {
      if (/^https?:\/\/[^/]*(youtube|google|ytimg|gstatic|doubleclick)/i.test(r.url())) fremd.push(r.url());
    });
    await zeile.click();
    await expect(page.getByTestId("youtube-consent")).toBeVisible({ timeout: 30_000 });
    await expect(page.locator("iframe")).toHaveCount(0);
    await expect(page.getByText(/here we are in front of the elephants/).first()).toBeVisible({ timeout: 30_000 });
    await page.waitForTimeout(1_500);
    expect(fremd).toEqual([]);
    await page.screenshot({ path: path.join(SHOTS, "youtube-e2e-04-flaeche.png") });
  } finally {
    await owner.delete(`/api/ai-assistant/workspaces/${angelegt.uuid}`);
  }
});

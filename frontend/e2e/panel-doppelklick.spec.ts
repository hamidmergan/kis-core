import { test, expect, type Page } from "@playwright/test";

/**
 * A double click on a panel header works like a window title bar: the panel
 * stays, the other two shrink to their strip, a second double click restores
 * the layout from before.
 */

const WORKSPACE = process.env.E2E_WORKSPACE ?? "1ea7b2fa-b237-4bbd-801b-c9793d388984";

test.use({ viewport: { width: 1600, height: 900 }, locale: "de-DE" });

const sources = (page: Page) => page.locator('[data-tour="sources-panel"]');
const chat = (page: Page) => page.locator('[data-tour="chat-panel"]');
const studio = (page: Page) => page.locator('[data-tour="studio-panel"]');
const header = (page: Page, title: string) =>
  page.locator("[data-panel-header]").filter({ hasText: title }).first();

test.beforeEach(async ({ page }) => {
  await page.addInitScript((uuid) => {
    localStorage.setItem(`ki-assistent-panels-${uuid}`, JSON.stringify({ quellen: true, chat: true, studio: true }));
  }, WORKSPACE);
  await page.goto(`/workspace/${WORKSPACE}`, { waitUntil: "domcontentloaded" });
  await expect(chat(page)).toBeVisible({ timeout: 30_000 });
  await page.waitForTimeout(1_500);
  await page.keyboard.press("Escape");
});

test("Doppelklick auf die Chat-Kopfzeile zeigt den Chat allein und stellt danach alles wieder her", async ({ page }) => {
  const chatBefore = (await chat(page).boundingBox())!.width;

  await header(page, "Chat").getByText("Chat", { exact: true }).dblclick();
  await expect(sources(page)).toHaveCount(0);
  await expect(studio(page)).toHaveCount(0);
  expect((await chat(page).boundingBox())!.width).toBeGreaterThan(chatBefore + 300);
  expect(await page.evaluate(() => window.getSelection()?.toString() ?? "")).toBe("");

  await header(page, "Chat").getByText("Chat", { exact: true }).dblclick();
  await expect(sources(page)).toBeVisible();
  await expect(studio(page)).toBeVisible();
  expect(Math.abs((await chat(page).boundingBox())!.width - chatBefore)).toBeLessThan(2);
});

test("Doppelklick auf Studio und Materialien wirkt genauso", async ({ page }) => {
  await header(page, "Studio").dblclick({ position: { x: 200, y: 20 } });
  await expect(sources(page)).toHaveCount(0);
  await expect(chat(page)).toHaveCount(0);
  await expect(studio(page)).toBeVisible();

  await header(page, "Studio").dblclick({ position: { x: 200, y: 20 } });
  await expect(sources(page)).toBeVisible();
  await expect(chat(page)).toBeVisible();

  await header(page, "Materialien").getByText("Materialien").dblclick();
  await expect(chat(page)).toHaveCount(0);
  await expect(studio(page)).toHaveCount(0);
  await header(page, "Materialien").getByText("Materialien").dblclick();
  await expect(chat(page)).toBeVisible();
  await expect(studio(page)).toBeVisible();
});

test("Doppelklick auf einen Knopf in der Kopfzeile ändert die Aufteilung nicht", async ({ page }) => {
  await header(page, "Chat").getByTitle("Optionen").dblclick();
  await expect(sources(page)).toBeVisible();
  await expect(studio(page)).toBeVisible();
});

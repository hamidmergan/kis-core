import { test, expect, devices } from "@playwright/test";

/**
 * A phone in landscape keeps the single-panel tab layout with a real height.
 * The old landscape flow mode collapsed the panel container to 0px because
 * the three panels are absolutely positioned inside it.
 */

const WORKSPACE = process.env.E2E_WORKSPACE ?? "1ea7b2fa-b237-4bbd-801b-c9793d388984";

// WebKit is not installed here, Chromium emulates the phone just as well.
test.use({ ...devices["iPhone 13 landscape"], defaultBrowserType: "chromium", locale: "de-DE" });

test("Handy in Querlage: Chat, Materialien und Viewer behalten ihre Höhe", async ({ page }) => {
  await page.goto(`/workspace/${WORKSPACE}`, { waitUntil: "domcontentloaded" });
  const chatTab = page.getByRole("button", { name: "Chat", exact: true });
  await expect(chatTab).toBeVisible({ timeout: 30_000 });
  await page.waitForTimeout(2_000);
  await page.keyboard.press("Escape");

  await chatTab.click();
  const chat = page.locator('[data-tour="chat-panel"]');
  const chatBox = await chat.boundingBox();
  expect(chatBox?.height ?? 0).toBeGreaterThan(150);
  await expect(chat.locator("textarea")).toBeInViewport();

  await page.getByRole("button", { name: "Materialien", exact: true }).click();
  // The first row sits at the top of the list, the PDF may need a scroll inside it.
  await expect(page.getByText(/\.webm$/i).first()).toBeInViewport();
  await page.getByText(/\.pdf$/i).first().click();
  const viewerBox = await page.locator('[data-tour="pdf-viewer"]').boundingBox();
  expect(viewerBox?.height ?? 0).toBeGreaterThan(150);

  // Nothing spills beyond the viewport, the page itself never scrolls.
  const scrollH = await page.evaluate(() => document.documentElement.scrollHeight);
  expect(scrollH).toBeLessThanOrEqual(page.viewportSize()!.height);
});

test("Handy: die Seitenhuelle folgt der sichtbaren Hoehe, sonst liegt der X-Knopf hinter der Browserleiste", async ({ page }) => {
  await page.goto(`/workspace/${WORKSPACE}`, { waitUntil: "domcontentloaded" });
  await expect(page.getByRole("button", { name: "Chat", exact: true })).toBeVisible({ timeout: 30_000 });
  const shell = await page.evaluate(() => {
    const el = document.querySelector(".viewport-shell");
    const rule = Array.from(document.styleSheets)
      .flatMap((s) => { try { return Array.from(s.cssRules); } catch { return []; } })
      .find((r): r is CSSStyleRule => r instanceof CSSStyleRule && r.selectorText === ".viewport-shell");
    return { height: rule?.style.height ?? null, bottom: el?.getBoundingClientRect().bottom ?? -1, inner: window.innerHeight };
  });
  // 100dvh wins where supported, 100vh stays as the fallback.
  expect(shell.height).toBe("100dvh");
  expect(shell.bottom).toBe(shell.inner);
});

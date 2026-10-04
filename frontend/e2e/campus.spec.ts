import { test, expect } from "@playwright/test";

/** The campus assistant answers with sources and keeps the chat in the history. */
test.describe("Campus-Assistent", () => {
  test("Beispielfrage bringt Antwort mit Quellen und legt einen Chat an", async ({ page }) => {
    await page.goto("/tools/campus", { waitUntil: "domcontentloaded" });
    await page.waitForSelector('[data-testid="campus-examples"]', { timeout: 30_000 });

    await page.locator('[data-testid="campus-examples"] button').nth(3).click();
    const answer = page.locator('[data-testid="assistant-message"]').first();
    await expect(answer).toBeVisible({ timeout: 30_000 });
    await expect(answer.locator('[data-testid="campus-sources"]')).toBeVisible({ timeout: 90_000 });

    // The question became the title of a new chat in the history.
    await expect(page.locator('[data-testid="campus-history"] li').first()).toBeVisible();
  });

  test("ein neuer Chat startet leer", async ({ page }) => {
    await page.goto("/tools/campus", { waitUntil: "domcontentloaded" });
    await page.locator('[data-testid="campus-new-chat"]').click();
    await expect(page.locator('[data-testid="campus-examples"]')).toBeVisible();
    await expect(page.locator('[data-testid="assistant-message"]')).toHaveCount(0);
  });
});

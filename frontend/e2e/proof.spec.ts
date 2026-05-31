import { test, expect } from "@playwright/test";
import { openWorkspace, askAndGetAnswer, chipsIn, highlightRectCount } from "./_chat";

// Visible proof run: capture screenshots so the live behaviour can be eyeballed.
test("proof: live answer + citation highlight", async ({ page }) => {
  await openWorkspace(page);
  const answer = await askAndGetAnswer(page, "Welche Zitierstile oder Zitierregeln werden genannt?");

  const pdfChip = chipsIn(answer, '[title*="p."]').first();
  await expect(pdfChip).toBeVisible({ timeout: 90_000 });

  // 1) The rendered answer with citation chips.
  await page.screenshot({ path: "e2e/screens/1-answer.png", fullPage: false });

  await pdfChip.click();
  await expect.poll(() => highlightRectCount(page), { timeout: 30_000 }).toBeGreaterThan(0);
  await page.waitForTimeout(1500);

  // 2) The viewer after the chip click — highlight visible on the cited page.
  await page.screenshot({ path: "e2e/screens/2-highlight.png", fullPage: false });

  console.log("RECTS:", await highlightRectCount(page));
});

import { test, expect } from "@playwright/test";
import { openWorkspace, askAndGetAnswer, chipsIn, highlightRectCount, revealChipsIn, selectOnlySourceByName } from "./_chat";

// Visible proof run: capture screenshots so the live behaviour can be eyeballed.
test("proof: live answer + nav-only citation (no highlight)", async ({ page }) => {
  await openWorkspace(page);
  // Scope to the citation-styles PDF so the cited chip is deterministically a PDF page.
  await selectOnlySourceByName(page, "WissenschaftlichesSchreiben");
  const answer = await askAndGetAnswer(page, "Welche Zitierstile oder Zitierregeln werden genannt?");

  // Stops hold their chips hidden until opened, so open them before reaching for one.
  await revealChipsIn(answer);
  const pdfChip = chipsIn(answer, '[title*="p."]').first();
  await expect(pdfChip).toBeVisible({ timeout: 90_000 });

  // 1) The rendered answer with citation chips.
  await page.screenshot({ path: "e2e/screens/1-answer.png", fullPage: false });

  await pdfChip.click();

  // Nav-only: the chip opens the PDF viewer to the cited page, but draws NO text
  // highlight (only the user's own popup/action-bar selection highlights).
  await expect(page.locator("embedpdf-container")).toBeVisible({ timeout: 30_000 });
  await page.waitForTimeout(1500);
  expect(await highlightRectCount(page)).toBe(0);

  // 2) The viewer after the chip click — cited page open, nav-only (no highlight).
  await page.screenshot({ path: "e2e/screens/2-navigation.png", fullPage: false });

  console.log("RECTS (nav-only, expect 0):", await highlightRectCount(page));
});

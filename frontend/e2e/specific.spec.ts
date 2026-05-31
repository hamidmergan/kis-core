import { test, expect } from "@playwright/test";
import {
  openWorkspace,
  askAndGetAnswer,
  selectOnlySourceByName,
  highlightRectCount,
  mediaCurrentTime,
  chipsIn,
} from "./_chat";

/**
 * SPECIFIC path: topic-focused questions routed to hybrid search, producing
 * keyword-grounded citations. The payoff we verify here is the user-visible
 * effect of clicking a citation: the viewer navigates AND highlights/seeks.
 */
test.describe("AIA chat — SPECIFIC path", () => {
  test("PDF citation click highlights the cited text in the viewer", async ({ page }) => {
    await openWorkspace(page);
    const answer = await askAndGetAnswer(page, "Welche Zitierstile oder Zitierregeln werden genannt?");

    const pdfChip = chipsIn(answer, '[title*="p."]').first();
    await expect(pdfChip).toBeVisible({ timeout: 90_000 });

    // No highlight before the click (viewer not showing this passage yet).
    expect(await highlightRectCount(page)).toBe(0);

    await pdfChip.click();

    // Clicking the chip opens the PDF and renders selection-rect highlights
    // over the grounded text inside the EmbedPDF shadow DOM.
    await expect
      .poll(() => highlightRectCount(page), { timeout: 30_000 })
      .toBeGreaterThan(0);
  });

  test("video timestamp citation click seeks the media player", async ({ page }) => {
    await openWorkspace(page);
    // Restrict to one lecture video so any citation is a timestamp into it.
    await selectOnlySourceByName(page, "VL1_25-03-2026");
    const answer = await askAndGetAnswer(page, "Worum geht es in dieser Vorlesung?");

    const tsChip = chipsIn(answer).filter({ hasText: /\d+:\d{2}/ }).first();
    await expect(tsChip).toBeVisible({ timeout: 90_000 });

    await tsChip.click();

    // The player seeks to the cited position (chips never cite 00:00 for content).
    await expect
      .poll(() => mediaCurrentTime(page), { timeout: 30_000 })
      .toBeGreaterThan(0.4);
  });
});

import { test, expect } from "@playwright/test";
import {
  openWorkspace,
  askAndGetAnswer,
  selectOnlySourceByName,
  highlightRectCount,
  mediaCurrentTime,
  chipsIn,
  revealChipsIn,
} from "./_chat";

/**
 * SPECIFIC path: topic-focused questions routed to hybrid search, producing
 * keyword-grounded citations. The payoff we verify here is the user-visible
 * effect of clicking a citation: the viewer NAVIGATES — a PDF chip opens the
 * cited page nav-only (no highlight), a media chip seeks the player. Citation
 * chips are nav-only; only the user's own popup/action-bar selection highlights.
 */
test.describe("AIA chat — SPECIFIC path", () => {
  test("PDF citation click opens the cited page nav-only (no text highlight)", async ({ page }) => {
    await openWorkspace(page);
    // Scope to the citation-styles PDF so the answer's citation is deterministically a
    // PDF page chip (with all 6 sources active it may cite a lecture video instead).
    await selectOnlySourceByName(page, "WissenschaftlichesSchreiben");
    const answer = await askAndGetAnswer(page, "Welche Zitierstile oder Zitierregeln werden genannt?");

    // Stops hold their chips hidden until opened, so open them before reaching for one.
    await revealChipsIn(answer);
    const pdfChip = chipsIn(answer, '[title*="p."]').first();
    await expect(pdfChip).toBeVisible({ timeout: 90_000 });

    // No PDF viewer open yet.
    expect(await highlightRectCount(page)).toBe(0);

    await pdfChip.click();

    // Nav-only: the chip opens the PDF viewer to the cited page (a flashing page
    // frame), but NEVER draws a text highlight inside the EmbedPDF shadow DOM.
    await expect(page.locator("embedpdf-container")).toBeVisible({ timeout: 30_000 });
    await page.waitForTimeout(1500); // give any would-be highlight time to render
    expect(await highlightRectCount(page)).toBe(0);
  });

  test("video timestamp citation click seeks the media player", async ({ page }) => {
    await openWorkspace(page);
    // Restrict to one lecture video so any citation is a timestamp into it.
    await selectOnlySourceByName(page, "VL1_25-03-2026");
    const answer = await askAndGetAnswer(page, "Worum geht es in dieser Vorlesung?");

    await revealChipsIn(answer);
    const tsChip = chipsIn(answer).filter({ hasText: /\d+:\d{2}/ }).first();
    await expect(tsChip).toBeVisible({ timeout: 90_000 });

    await tsChip.click();

    // The player seeks to the cited position (chips never cite 00:00 for content).
    await expect
      .poll(() => mediaCurrentTime(page), { timeout: 30_000 })
      .toBeGreaterThan(0.4);
  });
});

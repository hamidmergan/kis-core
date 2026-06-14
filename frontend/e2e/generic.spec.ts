import { test, expect } from "@playwright/test";
import { openWorkspace, askAndGetAnswer, selectOnlySourceByName, chipsIn, waitForChipIn } from "./_chat";

/**
 * GENERIC path: broad/overview questions that the intent classifier routes to
 * the summary-based context (page-/doc-summaries), across all sources or one.
 * Live LLM -> we assert the SHAPE (a cited answer arrives), not the wording.
 */
test.describe("AIA chat — GENERIC path", () => {
  test("overview question across all sources yields a cited answer", async ({ page }) => {
    await openWorkspace(page);
    const answer = await askAndGetAnswer(page, "Worum geht es in diesen Materialien insgesamt?");
    // A visible citation chip proves the answer rendered AND carried sources.
    await waitForChipIn(answer);
  });

  test("overview scoped to a single source cites only that source", async ({ page }) => {
    await openWorkspace(page);
    // Unique substring of one PDF's filename (DB source 1).
    await selectOnlySourceByName(page, "WissenschaftlichesSchreiben");
    const answer = await askAndGetAnswer(page, "Worum geht es in diesem Dokument?");
    await waitForChipIn(answer);
    // The only active source is that PDF, so EVERY citation must reference it.
    // Scope to real citation chips ([title]) — the group "+N" toggle is also a
    // .chip-cite but carries no title, so it would inject an empty string here.
    const titles = await chipsIn(answer, "[title]").evaluateAll((els) =>
      els.map((e) => e.getAttribute("title") || "")
    );
    expect(titles.length).toBeGreaterThan(0);
    for (const title of titles) expect(title).toMatch(/WissenschaftlichesSchreiben/);
  });
});

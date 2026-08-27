import { test, expect } from "@playwright/test";
import { openWorkspace, askAndGetAnswer, selectOnlySourceByName, chipsIn, waitForChipIn } from "./_chat";

/** Overview questions: the shape of the answer is checked, not the wording. */
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
    // Only real chips count, the expand button carries no title.
    const titles = await chipsIn(answer, "[title]").evaluateAll((els) =>
      els.map((e) => e.getAttribute("title") || "")
    );
    expect(titles.length).toBeGreaterThan(0);
    for (const title of titles) expect(title).toMatch(/WissenschaftlichesSchreiben/);
  });
});

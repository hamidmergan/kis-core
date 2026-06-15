import { Page, Locator, expect } from "@playwright/test";

/** Seeded dev workspace (owner = LDAP user `a`) with 3 PDFs + 3 lecture videos. */
export const WS =
  process.env.E2E_WORKSPACE ??
  "/en/workspace/1ea7b2fa-b237-4bbd-801b-c9793d388984";

/** Open the workspace and wait until the chat input + source list are ready. */
export async function openWorkspace(page: Page): Promise<void> {
  await page.goto(WS, { waitUntil: "domcontentloaded" });
  await page.waitForSelector("textarea", { timeout: 30_000 });
  // Sources default-select asynchronously after hydration; give them a beat so
  // the send button (disabled while no source is active) becomes usable.
  await page.waitForTimeout(2_500);
}

/** Type a question and submit it (Enter, matching the real keybinding). */
export async function ask(page: Page, question: string): Promise<void> {
  const ta = page.locator("textarea").first();
  await ta.fill(question);
  await ta.press("Enter");
}

/**
 * Ask a question and return a locator scoped to the NEW assistant message.
 *
 * The conversation is persisted per (workspace, user), so the panel shows prior
 * answers too. We anchor on the just-created assistant bubble (count grows by
 * one) instead of ".first()" — otherwise assertions hit stale historical chips.
 */
export async function askAndGetAnswer(page: Page, question: string): Promise<Locator> {
  const answers = page.locator('[data-testid="assistant-message"]');
  const before = await answers.count();
  await ask(page, question);
  await expect(answers).toHaveCount(before + 1, { timeout: 60_000 });
  return answers.last();
}

/** Citation chips inside a specific message bubble (optionally further filtered). */
export function chipsIn(answer: Locator, suffix = ""): Locator {
  return answer.locator(`.chip-cite${suffix}`);
}

/** Wait for the first citation chip within a given answer bubble. */
export async function waitForChipIn(answer: Locator): Promise<Locator> {
  const chip = chipsIn(answer).first();
  await expect(chip).toBeVisible({ timeout: 90_000 });
  return chip;
}

/**
 * Restrict the active source set to exactly one source, matched by a substring
 * of its filename. Deselects everything first, then ticks the matching row.
 */
export async function selectOnlySourceByName(page: Page, namePart: string): Promise<void> {
  // A ticked checkbox renders a Check icon; clear the current selection by
  // toggling every ticked box off (robust + language-agnostic, unlike relying
  // on the translated "Deselect all" label).
  const ticked = page.locator("button.source-checkbox:has(svg)");
  for (let guard = 0; (await ticked.count()) > 0 && guard < 20; guard++) {
    await ticked.first().click();
    await page.waitForTimeout(150);
  }
  const row = page.locator("div.group.relative").filter({ hasText: namePart }).first();
  await row.locator("button.source-checkbox").click();
  await page.waitForTimeout(300);
  // Self-verify: exactly one source is now active (else the scoping is a lie).
  await expect(page.locator("button.source-checkbox:has(svg)")).toHaveCount(1);
}

/**
 * Count citation text-highlight rects inside the EmbedPDF shadow DOM. A citation
 * highlight is a yellow fill in the brand highlight colour (#FFE14D = rgb(255,225,77));
 * we match THAT colour specifically, not "any absolutely-positioned background", so the
 * PDF page/text-layer backgrounds (also absolute) are not miscounted. With chat citations
 * now nav-only, a chip click navigates but draws no such fill, so this stays 0; only the
 * user's own popup/action-bar selection produces a highlight.
 */
export async function highlightRectCount(page: Page): Promise<number> {
  return page.evaluate(() => {
    const host = document.querySelector("embedpdf-container") as Element | null;
    const root = (host && (host as unknown as { shadowRoot: ShadowRoot }).shadowRoot) || null;
    if (!root) return 0;
    let n = 0;
    for (const el of Array.from(root.querySelectorAll<HTMLElement>("*"))) {
      const bg = getComputedStyle(el).backgroundColor || "";
      if (bg.includes("255, 225, 77")) n++; // CITATION_HL_COLOR (#FFE14D) fill
    }
    return n;
  });
}

/** Current playback position of the media player (-1 if no player mounted). */
export async function mediaCurrentTime(page: Page): Promise<number> {
  return page.evaluate(() => {
    const m = document.querySelector<HTMLMediaElement>("video, audio");
    return m ? m.currentTime : -1;
  });
}


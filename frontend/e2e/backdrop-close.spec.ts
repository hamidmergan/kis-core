import { test, expect, type Page } from "@playwright/test";

/** A dialog must not close while selecting text in an input field. */

async function openCreateModal(page: Page) {
  await page.goto("/en", { waitUntil: "domcontentloaded" });
  await page.getByRole("button", { name: /^Create/i }).first().click();
  const feld = page.locator("input[type='text']").first();
  await expect(feld).toBeVisible();
  return feld;
}

test("Markieren im Eingabefeld schliesst das Fenster nicht", async ({ page }) => {
  const feld = await openCreateModal(page);
  await feld.fill("Beispieltitel zum Markieren");

  // Press inside the field, drag over the backdrop, release there.
  const box = (await feld.boundingBox())!;
  await page.mouse.move(box.x + box.width - 12, box.y + box.height / 2);
  await page.mouse.down();
  await page.mouse.move(box.x + 8, box.y + box.height / 2, { steps: 8 });
  await page.mouse.move(box.x + 8, box.y - 160, { steps: 8 });
  await page.mouse.up();

  await expect(feld, "das Fenster ist beim Markieren zugegangen").toBeVisible();
  await expect(feld).toHaveValue("Beispieltitel zum Markieren");
});

test("ein echter Klick daneben schliesst weiterhin", async ({ page }) => {
  const feld = await openCreateModal(page);

  const box = (await feld.boundingBox())!;
  await page.mouse.click(box.x + 8, box.y - 160);

  await expect(feld).toBeHidden();
});

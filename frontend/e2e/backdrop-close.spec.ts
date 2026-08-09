import { test, expect, type Page } from "@playwright/test";

/**
 * Ein Fenster darf beim Markieren im Eingabefeld nicht zugehen.
 *
 * Wer in einem Feld markiert und die Maustaste ueber dem Hintergrund loslaesst, erzeugt
 * einen Klick auf dem Hintergrund, denn der Browser feuert `click` auf dem gemeinsamen
 * Elternteil von Druck und Loslassen. Ein `onClick={onClose}` am Hintergrund haelt das
 * faelschlich fuer "daneben geklickt" und schliesst mitten im Tippen.
 *
 * Geprueft wird am Anlegen-Fenster der Kursraeume, weil es ohne Vorbedingungen erreichbar
 * ist. Alle Fenster teilen sich denselben Helfer (``ui/backdropClose``), dessen
 * Entscheidung zusaetzlich als Unit-Test liegt.
 *
 * Beide Richtungen gehoeren hierher: ohne den zweiten Test waere ein Fenster, das gar
 * nicht mehr schliesst, ebenfalls gruen.
 */

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

  // Im Feld druecken, ueber den Hintergrund ziehen, dort loslassen.
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

import { test, expect } from "@playwright/test";
import { readHelpTree } from "../src/app/[locale]/hilfe/_lib/articles";

/** Opens every help article in both languages and checks that it really renders. */
const LOCALES = ["de", "en"] as const;
const BASE = process.env.E2E_BASE_URL ?? "http://localhost:3000";

function prefix(locale: string) {
  return locale === "de" ? "" : `/${locale}`;
}

for (const locale of LOCALES) {
  const tree = readHelpTree(locale);

  test.describe(`Hilfe ${locale}`, () => {
    for (const group of tree) {
      for (const article of group.articles) {
        test(`${article.slug} ${locale}`, async ({ page }) => {
          await page.context().addCookies([{ name: "NEXT_LOCALE", value: locale, url: BASE }]);
          const response = await page.goto(`${prefix(locale)}/hilfe/${article.slug}`, {
            waitUntil: "domcontentloaded",
          });
          expect(response?.status()).toBe(200);

          await expect(page.getByRole("heading", { level: 1, name: article.title })).toBeVisible();

          // Every picture the article points at has to load, not just exist in the markup.
          const images = page.locator("article img");
          for (let i = 0; i < (await images.count()); i++) {
            const ok = await images
              .nth(i)
              .evaluate((el: HTMLImageElement) => el.complete && el.naturalWidth > 0);
            expect(ok, `Bild ${i} in ${article.slug}`).toBe(true);
          }
        });
      }
    }
  });
}

test.describe("Vollbild", () => {
  test("ein Klick aufs Bild macht es gross, Escape schliesst wieder", async ({ page }) => {
    await page.goto("/hilfe/oberflaeche", { waitUntil: "domcontentloaded" });
    const picture = page.locator("article button:has(img)").first();
    await expect(picture).toBeVisible();
    await picture.click();

    const dialog = page.getByRole("dialog");
    await expect(dialog).toBeVisible();
    // The large version has to be the same file, not a second one.
    const small = await picture.locator("img").getAttribute("src");
    await expect(dialog.locator("img")).toHaveAttribute("src", String(small));
    // The page behind must not scroll away under the picture.
    await expect(page.locator("body")).toHaveCSS("overflow", "hidden");

    await page.keyboard.press("Escape");
    await expect(dialog).toHaveCount(0);
    await expect(page.locator("body")).not.toHaveCSS("overflow", "hidden");
  });

  test("ein Klick auf den Rand schliesst", async ({ page }) => {
    await page.goto("/hilfe/oberflaeche", { waitUntil: "domcontentloaded" });
    await page.locator("article button:has(img)").first().click();
    const dialog = page.getByRole("dialog");
    await expect(dialog).toBeVisible();
    await dialog.click({ position: { x: 5, y: 5 } });
    await expect(dialog).toHaveCount(0);
  });
});

test.describe("Auf dem Handy", () => {
  test.use({ viewport: { width: 390, height: 844 } });

  test("das Menue ist eingeklappt und der Artikel steht oben", async ({ page }) => {
    await page.goto("/hilfe/materialien", { waitUntil: "domcontentloaded" });

    const toggle = page.locator("nav button[aria-expanded]");
    await expect(toggle).toBeVisible();
    await expect(toggle).toHaveAttribute("aria-expanded", "false");
    // Die Artikelliste darf den Text nicht nach unten schieben.
    await expect(page.locator("nav a:visible")).toHaveCount(0);

    const heading = page.locator("article h1");
    const box = await heading.boundingBox();
    expect(box!.y).toBeLessThan(400);

    await toggle.click();
    expect(await page.locator("nav a:visible").count()).toBeGreaterThan(20);
  });

  test("die offene Liste ueberlappt den Artikel nicht", async ({ page }) => {
    await page.goto("/hilfe/oberflaeche", { waitUntil: "domcontentloaded" });
    await page.locator("nav button[aria-expanded]").click();
    await expect(page.locator("nav a").first()).toBeVisible();

    // Eine gedeckelte Hoehe ohne Scrollen laesst die Liste ueber den Artikel laufen.
    const ueberlauf = await page.locator("nav").evaluate((n) => ({
      sichtbar: n.clientHeight,
      inhalt: n.scrollHeight,
      scrollt: getComputedStyle(n).overflowY,
    }));
    expect(ueberlauf.inhalt).toBeLessThanOrEqual(ueberlauf.sichtbar + 1);
  });

  test("das Vollbild deckt den ganzen Schirm ab", async ({ page }) => {
    await page.goto("/hilfe/materialien", { waitUntil: "domcontentloaded" });
    await page.locator("article button:has(img)").first().click();

    const dialog = page.getByRole("dialog");
    await expect(dialog).toBeVisible();
    const box = await dialog.boundingBox();
    expect(box).toEqual({ x: 0, y: 0, width: 390, height: 844 });
    // Was oben liegt, faengt auch die Klicks ab.
    const treffer = await page.evaluate(() => {
      const el = document.elementFromPoint(10, 800);
      return el?.getAttribute("role") ?? el?.closest("[role]")?.getAttribute("role") ?? "";
    });
    expect(treffer).toBe("dialog");
  });
});

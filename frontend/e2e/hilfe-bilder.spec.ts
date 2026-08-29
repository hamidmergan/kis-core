import { test, expect, type Page } from "@playwright/test";

/**
 * Takes the screenshots the help articles use, in both UI languages. Run it again
 * whenever the interface changes: E2E_BASE_URL=http://localhost:3010 npx playwright test hilfe-bilder
 */
const LOCALES = ["de", "en"] as const;
const SIZE = { width: 1440, height: 900 };
const BASE = process.env.E2E_BASE_URL ?? "http://localhost:3000";
// Das Demo-Modul "Projektmanagement", damit in den Bildern keine echten Kursdaten stehen.
const WORKSPACE = process.env.E2E_WORKSPACE ?? "6f2d916b-94a3-403a-ab4d-9000699e5ef0";

/** One picture per page that needs nothing but its address. */
const PAGES: { name: string; path: string }[] = [
  { name: "startseite", path: "/" },
  { name: "werkzeug-uebersetzung", path: "/tools/translate" },
  { name: "werkzeug-vorlesen", path: "/tools/tts" },
  { name: "werkzeug-transkript", path: "/tools/stt" },
  { name: "werkzeug-zusammenfassung", path: "/tools/summarize" },
  { name: "werkzeug-bild", path: "/tools/image" },
  { name: "werkzeug-screencast", path: "/tools/screencast" },
  { name: "werkzeug-glossar", path: "/tools/glossary" },
  { name: "meine-jobs", path: "/my-jobs" },
];

/** Labels that differ per language, needed to click the right thing. */
const LABELS = {
  de: {
    tabSchedule: "Zeitplan",
    tabNotes: "Notizen",
    tabGlossary: "Glossar",
    tabStats: "Statistik",
    tileVocabCards: "Lernkarten",
    tileGrammar: "Grammatikübungen",
    tileVocabulary: "Wortschatzübungen",
    tileFlashcards: "Karteikarten",
    tileQuiz: "Quiz",
    tileMindmap: "Mindmap",
    tileTable: "Datentabelle",
    mindmapExpand: "Alle ausklappen",
    mindmapFull: "Vollbild",
    nextMonth: "Nächster Monat",
    expandBar: "Tools-Sidebar ausklappen",
  },
  en: {
    tabSchedule: "Schedule",
    tabNotes: "Notes",
    tabGlossary: "Glossary",
    tabStats: "Stats",
    tileVocabCards: "Vocab cards",
    tileGrammar: "Grammar exercises",
    tileVocabulary: "Vocabulary exercises",
    tileFlashcards: "Flashcards",
    tileQuiz: "Quiz",
    tileMindmap: "Mind map",
    tileTable: "Data table",
    mindmapExpand: "Expand all",
    mindmapFull: "Fullscreen",
    nextMonth: "Next month",
    expandBar: "Expand tools sidebar",
  },
} as const;

/** Nur die unkritische Admin-Seite: Nutzerliste und Anbieter zeigen Personendaten und Endpunkte. */
const ADMIN_PAGES: { name: string; path: string }[] = [
  { name: "verwaltung-werkzeuge", path: "/admin/werkzeuge/freigabe" },
];

/** German is the default locale and carries no prefix. */
function prefix(locale: string) {
  return locale === "de" ? "" : `/${locale}`;
}

function shot(locale: string, name: string) {
  return `public/hilfe/${locale}/${name}.png`;
}

/** The saved session carries a language cookie, without this every shot comes out English. */
async function useLocale(page: Page, locale: string) {
  await page.context().addCookies([{ name: "NEXT_LOCALE", value: locale, url: BASE }]);
}

async function settle(page: Page) {
  await expect(page.locator("header")).toBeVisible();
  await page.waitForTimeout(2000);
}

/** Opens the module, then a studio tile, then the first set inside it. */
async function openFirstSet(page: Page, locale: string, tile: string) {
  await page.goto(`${prefix(locale)}/workspace/${WORKSPACE}`, { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(4000);
  await page.getByText(tile, { exact: true }).first().click();
  await page.waitForTimeout(2500);
  // The set cards are the only clickable boxes in the list.
  await page.locator(".bg-background.rounded-xl").first().click();
  await page.waitForTimeout(3500);
}

test.describe("Hilfe-Bilder", () => {
  // Twice the pixels, so the pictures stay sharp when the article scales them.
  test.use({ viewport: SIZE, deviceScaleFactor: 2 });

  test.describe("ohne Anmeldung", () => {
    test.use({ storageState: { cookies: [], origins: [] } });

    for (const locale of LOCALES) {
      test(`anmeldung ${locale}`, async ({ page }) => {
        await useLocale(page, locale);
        await page.goto(`${prefix(locale)}/login`, { waitUntil: "domcontentloaded" });
        await page.waitForSelector("#username");
        // The card alone, without the welcome heading above it and its empty space.
        await page.locator(".max-w-sm > div").last().screenshot({ path: shot(locale, "anmeldung") });
      });
    }
  });

  for (const locale of LOCALES) {
    for (const entry of PAGES) {
      test(`${entry.name} ${locale}`, async ({ page }) => {
        await useLocale(page, locale);
        await page.goto(`${prefix(locale)}${entry.path}`, { waitUntil: "domcontentloaded" });
        await settle(page);
        await page.screenshot({ path: shot(locale, entry.name) });
      });
    }

    test(`kalender ${locale}`, async ({ page }) => {
      await useLocale(page, locale);
      await page.goto(`${prefix(locale)}/kalender`, { waitUntil: "domcontentloaded" });
      await settle(page);
      // Der laufende Monat ist leer, die Kurstermine liegen im Wintersemester.
      for (let i = 0; i < 4; i++) {
        await page.getByRole("button", { name: LABELS[locale].nextMonth }).click();
        await page.waitForTimeout(400);
      }
      await page.waitForTimeout(1500);
      await page.screenshot({ path: shot(locale, "kalender") });
    });

    test(`kopfleiste ${locale}`, async ({ page }) => {
      await useLocale(page, locale);
      await page.goto(`${prefix(locale)}/`, { waitUntil: "domcontentloaded" });
      await settle(page);
      await page.locator('header button[aria-haspopup="menu"]').last().click();
      await page.waitForTimeout(500);
      await page.screenshot({ path: shot(locale, "kopfleiste") });
    });

    for (const entry of ADMIN_PAGES) {
      test(`${entry.name} ${locale}`, async ({ page }) => {
        await useLocale(page, locale);
        await page.goto(`${prefix(locale)}${entry.path}`, { waitUntil: "domcontentloaded" });
        await settle(page);
        await page.screenshot({ path: shot(locale, entry.name) });
      });
    }

    test(`werkzeugleiste ${locale}`, async ({ page }) => {
      await useLocale(page, locale);
      await page.goto(`${prefix(locale)}/`, { waitUntil: "domcontentloaded" });
      await settle(page);
      // Unfolded, otherwise the picture is a column of icons without names.
      const expand = page.getByRole("button", { name: LABELS[locale].expandBar });
      if (await expand.count()) {
        await expand.first().click();
        await page.waitForTimeout(800);
      }
      // The bar alone, a whole page would drown it.
      await page.locator("aside, nav").first().screenshot({ path: shot(locale, "werkzeugleiste") });
    });

    test(`modul-anlegen ${locale}`, async ({ page }) => {
      await useLocale(page, locale);
      await page.goto(`${prefix(locale)}/`, { waitUntil: "domcontentloaded" });
      await settle(page);
      await page.locator('button:has-text("+")').last().click();
      await page.waitForTimeout(800);
      await page.screenshot({ path: shot(locale, "modul-anlegen") });
    });

    for (const [name, key] of [
      ["modul-zeitplan", "tabSchedule"],
      ["modul-notizen", "tabNotes"],
      ["modul-glossar", "tabGlossary"],
      ["modul-statistik", "tabStats"],
    ] as const) {
      test(`${name} ${locale}`, async ({ page }) => {
        await useLocale(page, locale);
        await page.goto(`${prefix(locale)}/workspace/${WORKSPACE}`, { waitUntil: "domcontentloaded" });
        await page.waitForTimeout(4000);
        await page.getByRole("button", { name: LABELS[locale][key], exact: true }).click();
        await page.waitForTimeout(2500);
        await page.screenshot({ path: shot(locale, name) });
      });
    }

    for (const [name, key] of [
      ["sprachtrainer-lernkarten", "tileVocabCards"],
      ["sprachtrainer-grammatik", "tileGrammar"],
      ["sprachtrainer-wortschatz", "tileVocabulary"],
    ] as const) {
      test(`${name} ${locale}`, async ({ page }) => {
        await useLocale(page, locale);
        await page.goto(`${prefix(locale)}/workspace/${WORKSPACE}`, { waitUntil: "domcontentloaded" });
        await page.waitForTimeout(4000);
        await page.getByText(LABELS[locale][key], { exact: true }).first().click();
        await page.waitForTimeout(2500);
        await page.screenshot({ path: shot(locale, name) });
      });
    }

    test(`modul-viewer ${locale}`, async ({ page }) => {
      await useLocale(page, locale);
      await page.goto(`${prefix(locale)}/workspace/${WORKSPACE}`, { waitUntil: "domcontentloaded" });
      await page.waitForTimeout(4000);
      // Irgendein PDF, unabhaengig davon wie die Dateien im Modul heissen.
      await page.locator('[title$=".pdf"]').first().click();
      // Das PDF rendert erst nach dem Laden, sonst steht "Loading document" im Bild.
      await expect(page.getByText(/Loading document/i)).toHaveCount(0, { timeout: 60_000 });
      await page.waitForTimeout(3000);
      await page.screenshot({ path: shot(locale, "modul-viewer") });
    });

    test(`modul-studio ${locale}`, async ({ page }) => {
      await useLocale(page, locale);
      await page.goto(`${prefix(locale)}/workspace/${WORKSPACE}`, { waitUntil: "domcontentloaded" });
      await page.waitForTimeout(4000);
      // By index it would grab a chat bubble, the tab strip identifies the panel.
      const studio = page
        .locator(".rounded-2xl")
        .filter({ hasText: LABELS[locale].tabSchedule })
        .last();
      await studio.screenshot({ path: shot(locale, "modul-studio") });
    });

    test(`modul-chat ${locale}`, async ({ page }) => {
      await useLocale(page, locale);
      await page.goto(`${prefix(locale)}/workspace/${WORKSPACE}`, { waitUntil: "domcontentloaded" });
      await page.waitForTimeout(4000);
      // The middle panel alone, the other two belong to other articles.
      await page.locator(".rounded-2xl").nth(1).screenshot({ path: shot(locale, "modul-chat") });
    });


    for (const [name, key] of [
      ["uebung-karteikarten", "tileFlashcards"],
      ["uebung-quiz", "tileQuiz"],
      ["uebung-lernkarten", "tileVocabCards"],
      ["uebung-wortschatz", "tileVocabulary"],
      ["uebung-grammatik", "tileGrammar"],
      ["modul-datentabelle", "tileTable"],
    ] as const) {
      test(`${name} ${locale}`, async ({ page }) => {
        await useLocale(page, locale);
        await openFirstSet(page, locale, LABELS[locale][key]);
        await page.screenshot({ path: shot(locale, name) });
      });
    }

    test(`modul-mindmap ${locale}`, async ({ page }) => {
      await useLocale(page, locale);
      await openFirstSet(page, locale, LABELS[locale].tileMindmap);
      // In the narrow panel only the root node is visible, so unfold and go fullscreen.
      await page.locator(`button[title="${LABELS[locale].mindmapExpand}"]`).first().click();
      await page.waitForTimeout(1200);
      await page.locator(`button[title="${LABELS[locale].mindmapFull}"]`).first().click();
      await page.waitForTimeout(2000);
      await page.screenshot({ path: shot(locale, "modul-mindmap") });
    });

    test(`modul-erstellen ${locale}`, async ({ page }) => {
      await useLocale(page, locale);
      await page.goto(`${prefix(locale)}/workspace/${WORKSPACE}`, { waitUntil: "domcontentloaded" });
      await page.waitForTimeout(4000);
      await page.getByText(LABELS[locale].tileFlashcards, { exact: true }).first().click();
      await page.waitForTimeout(2500);
      await page.getByRole("button", { name: /Erstellen|Create/ }).first().click();
      await page.waitForTimeout(1500);
      await page.screenshot({ path: shot(locale, "modul-erstellen") });
    });

    test(`modul-einstellungen ${locale}`, async ({ page }) => {
      await useLocale(page, locale);
      await page.goto(`${prefix(locale)}/workspace/${WORKSPACE}`, { waitUntil: "domcontentloaded" });
      await page.waitForTimeout(4000);
      // The small gear of the module, not the one in the header.
      await page.locator('button[title="Einstellungen"].w-7, button[title="Settings"].w-7').first().click();
      await page.waitForTimeout(1500);
      await page.screenshot({ path: shot(locale, "modul-einstellungen") });
    });


    // The round marks are toggles, the citations only unfold after a click.
    test(`modul-video ${locale}`, async ({ page }) => {
      await useLocale(page, locale);
      await page.goto(`${prefix(locale)}/workspace/${WORKSPACE}`, { waitUntil: "domcontentloaded" });
      await page.waitForTimeout(4000);
      await page.locator('[title$=".mp4"]').first().click();
      // Das Transkript laedt nach, sonst steht nur der Abspieler im Bild.
      await expect(page.getByText(/Transkript|Transcript/i).first()).toBeVisible({ timeout: 60_000 });
      await page.waitForTimeout(4000);
      await page.screenshot({ path: shot(locale, "modul-video") });
    });

    test(`modul-belege ${locale}`, async ({ page }) => {
      await useLocale(page, locale);
      await page.goto(`${prefix(locale)}/workspace/${WORKSPACE}`, { waitUntil: "domcontentloaded" });
      await page.waitForTimeout(4000);
      await page.locator('[data-testid="assistant-message"] .chip-toggle').first().click();
      await expect(page.locator(".chip-cite").first()).toBeVisible();
      await page.waitForTimeout(500);
      await page.screenshot({ path: shot(locale, "modul-belege") });
    });

    test(`modul-beleg-sprung ${locale}`, async ({ page }) => {
      await useLocale(page, locale);
      await page.goto(`${prefix(locale)}/workspace/${WORKSPACE}`, { waitUntil: "domcontentloaded" });
      await page.waitForTimeout(4000);
      await page.locator('[data-testid="assistant-message"] .chip-toggle').first().click();
      const chip = page.locator(".chip-cite").first();
      await expect(chip).toBeVisible();
      await chip.click();
      await page.waitForTimeout(5000);
      await page.screenshot({ path: shot(locale, "modul-beleg-sprung") });
    });

    test(`modul-ansicht ${locale}`, async ({ page }) => {
      await useLocale(page, locale);
      await page.goto(`${prefix(locale)}/workspace/${WORKSPACE}`, { waitUntil: "domcontentloaded" });
      await page.waitForTimeout(5000);
      await page.screenshot({ path: shot(locale, "modul-ansicht") });
    });
  }
});

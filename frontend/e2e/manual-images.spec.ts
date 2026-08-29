import { test, expect, type Page } from "@playwright/test";

/**
 * Takes the screenshots the documentation articles use, in both UI languages. Run it again
 * whenever the interface changes: E2E_BASE_URL=http://localhost:3010 npx playwright test manual-images
 */
const LOCALES = ["de", "en"] as const;
const SIZE = { width: 1440, height: 900 };
const BASE = process.env.E2E_BASE_URL ?? "http://localhost:3000";
// Das Demo-Modul "Projektmanagement", damit in den Bildern keine echten Kursdaten stehen.
const WORKSPACE = process.env.E2E_WORKSPACE ?? "6f2d916b-94a3-403a-ab4d-9000699e5ef0";

/** One picture per page that needs nothing but its address. */
const PAGES: { name: string; path: string }[] = [
  { name: "start-page", path: "/" },
  { name: "tool-translation", path: "/tools/translate" },
  { name: "tool-text-to-speech", path: "/tools/tts" },
  { name: "tool-speech-to-text", path: "/tools/stt" },
  { name: "tool-summary", path: "/tools/summarize" },
  { name: "tool-image", path: "/tools/image" },
  { name: "tool-screencast", path: "/tools/screencast" },
  { name: "tool-glossary", path: "/tools/glossary" },
  { name: "my-jobs", path: "/my-jobs" },
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
    allMoods: "Alle Stimmungen nebeneinander",
    showAllCitations: "Alle Belege einblenden",
    diagResetLevel: "Ergebnis löschen",
    diagSkip: "Überspringen",
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
    allMoods: "All moods side by side",
    showAllCitations: "Show all citations",
    diagResetLevel: "Delete result",
    diagSkip: "Skip",
  },
} as const;

/** Nur die unkritische Admin-Seite: Nutzerliste und Anbieter zeigen Personendaten und Endpunkte. */
const ADMIN_PAGES: { name: string; path: string }[] = [
  { name: "admin-tool-release", path: "/admin/werkzeuge/freigabe" },
];

/** German is the default locale and carries no prefix. */
function prefix(locale: string) {
  return locale === "de" ? "" : `/${locale}`;
}

function shot(locale: string, name: string) {
  return `public/manual/${locale}/${name}.png`;
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

test.describe("Handbuch-Bilder", () => {
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
        await page.locator(".max-w-sm > div").last().screenshot({ path: shot(locale, "sign-in") });
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
      await page.screenshot({ path: shot(locale, "calendar") });
    });

    test(`kopfleiste ${locale}`, async ({ page }) => {
      await useLocale(page, locale);
      await page.goto(`${prefix(locale)}/`, { waitUntil: "domcontentloaded" });
      await settle(page);
      await page.locator('header button[aria-haspopup="menu"]').last().click();
      await page.waitForTimeout(500);
      await page.screenshot({ path: shot(locale, "header-menu") });
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
      await page.locator("aside, nav").first().screenshot({ path: shot(locale, "tool-bar") });
    });

    test(`modul-anlegen ${locale}`, async ({ page }) => {
      await useLocale(page, locale);
      await page.goto(`${prefix(locale)}/`, { waitUntil: "domcontentloaded" });
      await settle(page);
      await page.locator('button:has-text("+")').last().click();
      await page.waitForTimeout(800);
      await page.screenshot({ path: shot(locale, "create-module") });
    });

    for (const [name, key] of [
      ["schedule-tab", "tabSchedule"],
      ["notes-tab", "tabNotes"],
      ["glossary-tab", "tabGlossary"],
      ["statistics-tab", "tabStats"],
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
      ["vocabulary-card-sets", "tileVocabCards"],
      ["grammar-sets", "tileGrammar"],
      ["vocabulary-exercise-sets", "tileVocabulary"],
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
      await page.screenshot({ path: shot(locale, "viewer") });
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
      await studio.screenshot({ path: shot(locale, "studio") });
    });

    test(`modul-chat ${locale}`, async ({ page }) => {
      await useLocale(page, locale);
      await page.goto(`${prefix(locale)}/workspace/${WORKSPACE}`, { waitUntil: "domcontentloaded" });
      await page.waitForTimeout(4000);
      // The middle panel alone, the other two belong to other articles.
      await page.locator(".rounded-2xl").nth(1).screenshot({ path: shot(locale, "chat") });
    });


    for (const [name, key] of [
      ["flashcard", "tileFlashcards"],
      ["quiz-question", "tileQuiz"],
      ["vocabulary-card", "tileVocabCards"],
      ["vocabulary-exercise", "tileVocabulary"],
      ["grammar-exercise", "tileGrammar"],
      ["data-table", "tileTable"],
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
      await page.screenshot({ path: shot(locale, "mind-map") });
    });

    test(`modul-erstellen ${locale}`, async ({ page }) => {
      await useLocale(page, locale);
      await page.goto(`${prefix(locale)}/workspace/${WORKSPACE}`, { waitUntil: "domcontentloaded" });
      await page.waitForTimeout(4000);
      await page.getByText(LABELS[locale].tileFlashcards, { exact: true }).first().click();
      await page.waitForTimeout(2500);
      await page.getByRole("button", { name: /Erstellen|Create/ }).first().click();
      await page.waitForTimeout(1500);
      await page.screenshot({ path: shot(locale, "create-set") });
    });

    test(`modul-einstellungen ${locale}`, async ({ page }) => {
      await useLocale(page, locale);
      await page.goto(`${prefix(locale)}/workspace/${WORKSPACE}`, { waitUntil: "domcontentloaded" });
      await page.waitForTimeout(4000);
      // The small gear of the module, not the one in the header.
      await page.locator('button[title="Einstellungen"].w-7, button[title="Settings"].w-7').first().click();
      await page.waitForTimeout(1500);
      await page.screenshot({ path: shot(locale, "module-settings") });
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
      await page.screenshot({ path: shot(locale, "video") });
    });

    test(`modul-belege ${locale}`, async ({ page }) => {
      await useLocale(page, locale);
      await page.goto(`${prefix(locale)}/workspace/${WORKSPACE}`, { waitUntil: "domcontentloaded" });
      await page.waitForTimeout(4000);
      await page.locator('[data-testid="assistant-message"] .chip-toggle').first().click();
      await expect(page.locator(".chip-cite").first()).toBeVisible();
      await page.waitForTimeout(500);
      await page.screenshot({ path: shot(locale, "citations") });
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
      await page.screenshot({ path: shot(locale, "citation-jump") });
    });

    test(`modul-ansicht ${locale}`, async ({ page }) => {
      await useLocale(page, locale);
      await page.goto(`${prefix(locale)}/workspace/${WORKSPACE}`, { waitUntil: "domcontentloaded" });
      await page.waitForTimeout(5000);
      await page.screenshot({ path: shot(locale, "module-view") });
    });

    // Die Auswahlleiste erscheint erst an einer echten Textauswahl. EmbedPDF malt die
    // Seite auf ein Canvas, es gibt keine Textschicht zum Anklicken, also zieht der
    // Zeiger ueber die Stelle im Demo-Foliensatz, an der die Aufzaehlung steht.
    test(`auswahlleiste ${locale}`, async ({ page }) => {
      await useLocale(page, locale);
      await page.goto(`${prefix(locale)}/workspace/${WORKSPACE}`, { waitUntil: "domcontentloaded" });
      await page.waitForTimeout(4000);
      await page.locator('[title$=".pdf"]').first().click();
      await expect(page.getByText(/Loading document/i)).toHaveCount(0, { timeout: 60_000 });
      await page.waitForTimeout(6000);
      const panel = (await page.locator(".viewer-short").first().boundingBox())!;
      await page.mouse.move(panel.x + 44, panel.y + 400);
      await page.mouse.down();
      await page.mouse.move(panel.x + 282, panel.y + 428, { steps: 20 });
      await page.mouse.up();
      await page.waitForTimeout(1800);
      await page.screenshot({
        path: shot(locale, "selection-bar"),
        clip: { x: panel.x + 6, y: panel.y + 358, width: 400, height: 140 },
      });
    });

    // Der Knopf steht nur beim Darueberfahren, eingeschaltet bleibt er sichtbar.
    test(`belege-knopf ${locale}`, async ({ page }) => {
      await useLocale(page, locale);
      await page.goto(`${prefix(locale)}/workspace/${WORKSPACE}`, { waitUntil: "domcontentloaded" });
      await page.waitForTimeout(5000);
      const answer = page.locator('[data-testid="assistant-message"]').last();
      await answer.hover();
      await answer.getByTitle(LABELS[locale].showAllCitations).click();
      await page.waitForTimeout(800);
      // Die Zeile unter der Antwort: links die Quellenzahl, rechts die Knoepfe.
      await answer.locator("div.justify-between").first().screenshot({
        path: shot(locale, "citations-toggle"),
      });
    });

    // Beide Knoepfe an der Markierung, der Pfeil kommt erst nach dem Weiterblaettern.
    test(`markierung-knoepfe ${locale}`, async ({ page }) => {
      await useLocale(page, locale);
      await page.goto(`${prefix(locale)}/workspace/${WORKSPACE}`, { waitUntil: "domcontentloaded" });
      await page.waitForTimeout(5000);
      const answer = page.locator('[data-testid="assistant-message"]').last();
      await answer.locator(".chip-toggle").first().click();
      const chip = answer.locator(".chip-cite").first();
      await expect(chip).toBeVisible();
      await chip.click();
      await page.waitForTimeout(6000);
      const bar = page.locator("div.absolute.bottom-6.right-4").first();
      await expect(bar).toBeVisible();
      const panel = (await page.locator(".viewer-short").first().boundingBox())!;
      // Weiterblaettern, sonst fehlt der Pfeil zurueck zur Stelle.
      for (let i = 0; i < 6 && (await bar.locator("button").count()) < 2; i++) {
        await page.mouse.move(panel.x + panel.width / 2, panel.y + panel.height / 2);
        await page.mouse.wheel(0, 1200);
        await page.waitForTimeout(1200);
      }
      const box = (await bar.boundingBox())!;
      // Etwas Umgebung mit im Bild, sonst schweben zwei Knoepfe im Nichts.
      await page.screenshot({
        path: shot(locale, "highlight-controls"),
        clip: { x: box.x - 200, y: box.y - 80, width: box.width + 220, height: box.height + 110 },
      });
    });

    // Nur das Raster mit den fuenf Stimmungen, der Rest der Seite ist Werkstatt.
    // Das Bild gibt es nur auf Deutsch, der englische Artikel zeigt dasselbe.
    test(`maskottchen-zustaende ${locale}`, async ({ page }) => {
      test.skip(locale !== "de", "ein Bild fuer beide Sprachen");
      await useLocale(page, locale);
      await page.goto(`${prefix(locale)}/admin/mascots/hilde`, { waitUntil: "domcontentloaded" });
      await settle(page);
      const section = page.locator("section").filter({ hasText: LABELS[locale].allMoods }).last();
      // Nur die Kaesten, die Ueberschrift darueber gehoert zur Verwaltung.
      const grid = section.locator("div.grid").first();
      await expect(grid).toBeVisible();
      // Die Figuren laufen beim Erscheinen eine Animation.
      await page.waitForTimeout(3000);
      await grid.screenshot({ path: shot(locale, "mascot-states") });
    });

    // Deletes the demo user's language level to reveal the test screen, then skips every
    // question to restore a level afterwards — must stay the LAST test per locale so no
    // other screenshot runs while the chat slot shows the diagnosis panel instead of chat.
    // The questions themselves are always German, regardless of the interface locale, so
    // one picture serves both articles (like mascot-states above).
    test(`sprachtest ${locale}`, async ({ page }) => {
      test.skip(locale !== "de", "ein Bild fuer beide Sprachen");
      await useLocale(page, locale);
      await page.goto(`${prefix(locale)}/workspace/${WORKSPACE}`, { waitUntil: "domcontentloaded" });
      await page.waitForTimeout(4000);
      await page.locator('button[title="Einstellungen"].w-7, button[title="Settings"].w-7').first().click();
      await page.waitForTimeout(500);
      page.once("dialog", (dialog) => dialog.accept());
      await page.getByRole("button", { name: LABELS[locale].diagResetLevel }).click();
      await page.keyboard.press("Escape");
      const skip = page.getByRole("button", { name: LABELS[locale].diagSkip });
      await expect(skip.first()).toBeVisible({ timeout: 15_000 });
      await page.waitForTimeout(1000);
      await page.locator(".rounded-2xl").nth(1).screenshot({ path: shot(locale, "language-test") });
      for (let i = 0; i < 12 && (await skip.count()); i++) {
        await skip.first().click();
        await page.waitForTimeout(1200);
      }
    });
  }
});

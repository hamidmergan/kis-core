// Zweisprachigkeit (Deutsch / Englisch)
//
// Sprache wird bestimmt durch (in dieser Reihenfolge):
//   1. URL-Parameter ?lang=en|de (z.B. fuer Einbettungen per iframe)
//   2. gespeicherte Auswahl im localStorage
//   3. Standard: Deutsch
//
// UI-Texte stehen in UI_STRINGS und werden per t('schluessel') geholt.
// Statische Texte in index.html tragen data-i18n-Attribute.
// Inhalte (Quizze, Gebaeude, Badges) bleiben in config_v2.js auf Deutsch;
// content_en.js legt die englischen Texte per applyContentOverlay() darueber.

const LANG_STORAGE_KEY = 'campusmap_lang';
const SUPPORTED_LANGS = ['de', 'en'];
const DEFAULT_LANG = 'de';
// Nach einem Sprachwechsel wird die Seite neu geladen. Das Intro soll dabei
// nicht erneut abgespielt werden.
const LANG_SWITCH_FLAG = 'campusmap_lang_switched';

function readStoredLang() {
    try {
        return localStorage.getItem(LANG_STORAGE_KEY);
    } catch (e) {
        return null;
    }
}

function detectLang() {
    const fromUrl = new URLSearchParams(window.location.search).get('lang');
    if (SUPPORTED_LANGS.includes(fromUrl)) return fromUrl;
    const stored = readStoredLang();
    if (SUPPORTED_LANGS.includes(stored)) return stored;
    return DEFAULT_LANG;
}

const CURRENT_LANG = detectLang();
document.documentElement.lang = CURRENT_LANG;

// ?partner=kis: KIS zeigt die Karte auf einer eigenen Seite und setzt sein Logo vor den Titel.
if (new URLSearchParams(window.location.search).get('partner') === 'kis') {
    document.documentElement.classList.add('partner-kis');
    // KIS passes its own addresses; only web links are accepted.
    const params = new URLSearchParams(window.location.search);
    const setPartnerLink = (id, name) => {
        const el = document.getElementById(id);
        const value = params.get(name) || '';
        if (el && /^https?:\/\//i.test(value)) el.href = value;
        else if (el) el.hidden = true;
    };
    document.addEventListener('DOMContentLoaded', () => {
        setPartnerLink('partnerHome', 'home');
    });
}

// true, wenn diese Seite durch einen Sprachwechsel neu geladen wurde
const CAME_FROM_LANG_SWITCH = (() => {
    try {
        const flag = sessionStorage.getItem(LANG_SWITCH_FLAG) === '1';
        sessionStorage.removeItem(LANG_SWITCH_FLAG);
        return flag;
    } catch (e) {
        return false;
    }
})();

const UI_STRINGS = {
    de: {
        // Seite & Kopfzeile
        'page.title': 'Campusplan – Technische Hochschule Lübeck',
        'skip.toMap': 'Direkt zur Karte',
        'header.title': 'Campusplan',
        'partner.home': 'KIS Startseite',
        'toolbox.settings': 'Einstellungen',
        'toolbox.badges': 'Badges',
        'toolbox.menu': 'Menü',
        'lang.label': 'Sprache',
        'common.close': 'Schließen',

        // Gebäude & Legende
        'legend.title': 'Gebäude',
        'legend.searchPlaceholder': 'Gebäude, Einrichtung oder Nummer',
        'legend.searchLabel': 'Campus durchsuchen',
        'legend.searchButtonTitle': 'Campus durchsuchen (Leertaste)',
        'legend.searchKey': 'Leertaste',
        'legend.shortcutTip': 'Tipp:',
        'legend.shortcutText': 'öffnet das Suchfenster',
        'legend.searchResults': 'Suchergebnisse',
        'legend.clear': 'Suche leeren',
        'legend.facilities': 'Einrichtungen',
        'legend.popular': 'Häufig gesucht',
        'legend.allFacilities': 'Alle Einrichtungen A–Z',
        'legend.formerly': 'früher {old}',
        'legend.inBuildings': 'in {n} Gebäuden',
        'legend.resultsPlaces': 'Gebäude & Orte',
        'legend.resultsCount': '{n} Treffer',
        'legend.noResults': 'Nichts gefunden für „{q}“',
        'legend.noResultsHint': 'Probier eine Gebäudenummer wie A.1, eine alte Nummer wie 36 oder einen Begriff wie Mensa.',
        'legend.fuzzyHint': 'Kein genauer Treffer für „{q}“ – meintest du das?',
        'legend.back': 'Gebäude',
        'legend.backLabel': 'Zurück zur Gebäudeübersicht',
        'legend.showOnMap': 'Auf Karte zeigen',
        'legend.pinLabel': '{name} auf der Karte zeigen',
        'legend.pillInfo': 'Infos anzeigen',
        'legend.pillMarked': '{n} Stationen markiert',
        'legend.pillMarkedPlaces': '{n} Orte markiert',
        'share.title': 'Link zu diesem Ort',
        'share.button': 'Link teilen',
        'share.copied': 'Link kopiert',
        'share.copyFailed': 'Link markiert – mit Strg+C / ⌘C kopieren',
        'share.copy': 'Link kopieren',
        'legend.markAll': 'Alle {n} Stationen auf der Karte markieren',
        'legend.pillClose': 'Hinweis schließen',

        // Einstellungen
        'settings.title': 'Einstellungen',
        'settings.close': 'Einstellungen schließen',
        'settings.display': 'Anzeige',
        'settings.animations': 'Animationen',
        'settings.mapElements': 'Kartenelemente',
        'settings.downloads': 'Downloads',
        'settings.pdf': 'Campusplan als PDF',
        'settings.legal': 'Rechtliches',
        'settings.imprint': 'Impressum',
        'settings.privacy': 'Datenschutz',
        'common.newTab': '(öffnet in neuem Tab)',
        'filters.showAll': 'Alle einblenden',
        'filters.hideAll': 'Alle ausblenden',
        'reset.title': 'Fortschritt zurücksetzen',
        'reset.question': 'Möchtest du nochmal von vorne beginnen?',
        'reset.confirmTitle': 'Fortschritt zurücksetzen?',
        'reset.item1': 'Alle abgeschlossenen Quizze werden zurückgesetzt',
        'reset.item2': 'Alle freigeschalteten Badges werden zurückgesetzt',
        'reset.item3': 'Du kannst die Badges erneut freischalten',
        'reset.confirmQuestion': 'Jetzt zurücksetzen?',
        'reset.cancel': 'Abbrechen',
        'reset.confirm': 'Zurücksetzen',

        // Intro
        'intro.skipTap': 'Tippen zum Überspringen',
        'intro.skipClick': 'Klicken zum Überspringen',
        'map.unavailable': 'Karte nicht verfügbar.',

        // Quiz allgemein
        'quiz.close': 'Quiz schließen',
        'quiz.check': 'Prüfen',
        'quiz.retry': 'Nochmal versuchen',
        'quiz.restart': 'Neu starten',
        'quiz.correct': 'Richtig!',
        'quiz.wrong': 'Leider falsch. Versuche es noch einmal.',
        'quiz.found': '{n} / {total} gefunden',
        'quiz.infoShow': 'Campus-Info anzeigen',
        'quiz.infoHide': 'Campus-Info schließen',

        // Sortieren
        'sort.up': 'Nach oben: {item}',
        'sort.down': 'Nach unten: {item}',
        'sort.correct': 'Richtige Reihenfolge!',
        'sort.wrong': 'Noch nicht ganz. Schau dir die rot markierten Schritte an und versuche es noch einmal.',
        'sort.item': 'Eintrag',
        'sort.position': '{item}: Position {i} von {n}',

        // Kreuzworträtsel
        'cw.across': 'Waagerecht',
        'cw.down': 'Senkrecht',
        'cw.dirAcross': 'waagerecht',
        'cw.dirDown': 'senkrecht',
        'cw.cell': '{num} {dir}, Buchstabe {i} von {n}',
        'cw.libError': 'Kreuzworträtsel-Bibliothek konnte nicht geladen werden.',
        'cw.solved': 'Super! Kreuzworträtsel gelöst.',
        'cw.missing': 'Es fehlen noch Buchstaben.',
        'cw.wrongLetters': 'Ein paar Buchstaben sind noch falsch (rot markiert).',

        // Suchbild
        'hotspot.done': 'Super! Alle Sicherheitsmängel gefunden.',
        'hotspot.gridLabel': 'Bildbereiche zum Absuchen: {rows} Zeilen, {cols} Spalten',
        'hotspot.region': 'Bildbereich Zeile {r}, Spalte {c}',
        'hotspot.hit': 'Richtig: {label}. {progress}',
        'hotspot.miss': 'In Zeile {r}, Spalte {c} ist nichts zu finden.',

        // Wortsuche
        'ws.hint': 'Hilfe',
        'ws.libError': 'Wortsuch-Bibliothek konnte nicht geladen werden.',
        'ws.createError': 'Rätsel konnte nicht erstellt werden.',
        'ws.cell': '{letter}, Zeile {r}, Spalte {c}',
        'ws.gridLabel': 'Buchstabenraster. Mit den Pfeiltasten bewegen, Enter setzt Anfang und Ende eines Wortes, Escape bricht ab.',
        'ws.done': 'Super! Alle Begriffe gefunden.',
        'ws.cancelled': 'Auswahl abgebrochen',
        'ws.anchorSet': 'Anfang gesetzt bei {letter}. Jetzt zum letzten Buchstaben gehen und erneut bestätigen.',
        'ws.straightOnly': 'Nur gerade Linien sind möglich: waagerecht, senkrecht oder diagonal.',
        'ws.wordFound': '{word} gefunden. {n} von {total} Wörtern.',
        'ws.wordWrong': '{word} ist keines der gesuchten Wörter.',

        // Memory
        'memory.reshuffle': 'Neu mischen',
        'memory.pairs': '{n} / {total} Paaren',
        'memory.done': 'Super! Alle Paare gefunden.',
        'memory.image': 'Bild',
        'memory.card': 'Karte {i} von {n}',
        'memory.cardHidden': '{pos}, verdeckt',
        'memory.cardOpen': '{pos}, aufgedeckt: {name}',
        'memory.cardMatched': '{pos}, {name}, Paar gefunden',
        'memory.turned': 'Aufgedeckt: {names}',
        'memory.noPair': '. Kein Paar. Beim nächsten Zug werden beide Karten wieder verdeckt.',
        'memory.pairsFound': '{n} von {total} Paaren gefunden',

        // Gebäude-Info
        'building.imageAlt': '{title} – Bild {i} von {n}',
        'carousel.prev': 'Vorheriges Bild',
        'carousel.next': 'Nächstes Bild',
        'carousel.goto': 'Bild {i} von {n}',
        'carousel.pause': 'Bildwechsel anhalten',
        'carousel.play': 'Bildwechsel fortsetzen',

        // Badges
        'badges.quizzes': '{n}/{total} Quizze',
        'badges.achieved': 'Erreicht!',
        'badges.remainingOne': 'Noch 1 Quiz!',
        'badges.remainingMany': 'Noch {n} Quizze!',
        'badges.earned': 'Badge erhalten:',
        'badges.closeNotification': 'Benachrichtigung schließen',

        // Karte (Screenreader)
        'map.containerLabel': 'Interaktiver Campusplan der TH Lübeck',
        'map.svgLabel': 'Campusplan mit Gebäuden, Quizzen und Serviceorten',
        'map.group.buildings': 'Gebäude',
        'map.group.cafes': 'Cafés und Kioske',
        'map.group.bikes': 'Fahrradstationen',
        'map.group.bus': 'Bushaltestellen',
        'map.group.links': 'Weiterführende Links',
        'map.group.quizzes': 'Quizze',
        'map.type.building': 'Gebäude',
        'map.type.cafe': 'Café',
        'map.type.bike': 'Fahrradstation',
        'map.type.bus': 'Bushaltestelle',
        'map.type.quiz': 'Quiz',
        'map.type.link': 'Link',
        'map.towards': 'Richtung {place}',
        'map.solved': ' – bereits gelöst',
        'map.newWindow': '(öffnet in neuem Fenster)',
        'map.logo': 'Website der TH Lübeck',
        'map.btn.Button_Studium': 'Studiengänge der TH Lübeck',
        'map.btn.Button_Speiseplan': 'Speiseplan der Mensa',
        'map.btn.Button_Erkundungstour': 'Erkundungstour: Film über die TH Lübeck',
        'map.btn.Button_Hochschulsport': 'Hochschulsport Lübeck',
        'map.btn.Button_FabLab': 'FabLab Lübeck',
        'map.btn.Button_Innenstadt': 'Lübecker Altstadt',
        'map.controls': 'Kartenansicht',
        'map.zoomIn': 'Karte vergrößern',
        'map.zoomOut': 'Karte verkleinern',

        // Ansagen
        'announce.mapElements': 'Kartenelemente',
        'announce.shown': '{name} eingeblendet',
        'announce.hidden': '{name} ausgeblendet',
        'announce.animOn': 'Animationen eingeschaltet',
        'announce.animOff': 'Animationen ausgeschaltet',
        'announce.allShown': 'Alle Kartenelemente eingeblendet',
        'announce.allHidden': 'Alle Kartenelemente ausgeblendet'
    },
    en: {
        // Page & header
        'page.title': 'Campus Map – Technische Hochschule Lübeck',
        'skip.toMap': 'Skip to map',
        'header.title': 'Campus Map',
        'partner.home': 'KIS home page',
        'toolbox.settings': 'Settings',
        'toolbox.badges': 'Badges',
        'toolbox.menu': 'Menu',
        'lang.label': 'Language',
        'common.close': 'Close',

        // Buildings & legend
        'legend.title': 'Buildings',
        'legend.searchPlaceholder': 'Building, service or number',
        'legend.searchLabel': 'Search the campus',
        'legend.searchButtonTitle': 'Search the campus (Space)',
        'legend.searchKey': 'Space',
        'legend.shortcutTip': 'Tip:',
        'legend.shortcutText': 'opens the search window',
        'legend.searchResults': 'Search results',
        'legend.clear': 'Clear search',
        'legend.facilities': 'Facilities',
        'legend.popular': 'Popular',
        'legend.allFacilities': 'All facilities A–Z',
        'legend.formerly': 'formerly {old}',
        'legend.inBuildings': 'in {n} buildings',
        'legend.resultsPlaces': 'Buildings & places',
        'legend.resultsCount': '{n} results',
        'legend.noResults': 'No results for “{q}”',
        'legend.noResultsHint': 'Try a building number like A.1, an old number like 36 or a term like Mensa.',
        'legend.fuzzyHint': 'No exact match for “{q}” – did you mean this?',
        'legend.back': 'Buildings',
        'legend.backLabel': 'Back to the building overview',
        'legend.showOnMap': 'Show on map',
        'legend.pinLabel': 'Show {name} on the map',
        'legend.pillInfo': 'Show info',
        'legend.pillMarked': '{n} stations marked',
        'legend.pillMarkedPlaces': '{n} places marked',
        'share.title': 'Link to this place',
        'share.button': 'Share link',
        'share.copied': 'Link copied',
        'share.copyFailed': 'Link selected – press Ctrl+C / ⌘C to copy',
        'share.copy': 'Copy link',
        'legend.markAll': 'Mark all {n} stations on the map',
        'legend.pillClose': 'Dismiss',

        // Settings
        'settings.title': 'Settings',
        'settings.close': 'Close settings',
        'settings.display': 'Display',
        'settings.animations': 'Animations',
        'settings.mapElements': 'Map elements',
        'settings.downloads': 'Downloads',
        'settings.pdf': 'Campus map as PDF',
        'settings.legal': 'Legal',
        'settings.imprint': 'Imprint',
        'settings.privacy': 'Privacy policy',
        'common.newTab': '(opens in new tab)',
        'filters.showAll': 'Show all',
        'filters.hideAll': 'Hide all',
        'reset.title': 'Reset progress',
        'reset.question': 'Want to start over from the beginning?',
        'reset.confirmTitle': 'Reset progress?',
        'reset.item1': 'All completed quizzes will be reset',
        'reset.item2': 'All unlocked badges will be reset',
        'reset.item3': 'You can unlock the badges again',
        'reset.confirmQuestion': 'Reset now?',
        'reset.cancel': 'Cancel',
        'reset.confirm': 'Reset',

        // Intro
        'intro.skipTap': 'Tap to skip',
        'intro.skipClick': 'Click to skip',
        'map.unavailable': 'Map not available.',

        // Quiz general
        'quiz.close': 'Close quiz',
        'quiz.check': 'Check',
        'quiz.retry': 'Try again',
        'quiz.restart': 'Restart',
        'quiz.correct': 'Correct!',
        'quiz.wrong': 'Not quite. Give it another try.',
        'quiz.found': '{n} / {total} found',
        'quiz.infoShow': 'Show campus info',
        'quiz.infoHide': 'Close campus info',

        // Sort
        'sort.up': 'Move up: {item}',
        'sort.down': 'Move down: {item}',
        'sort.correct': 'Correct order!',
        'sort.wrong': 'Not quite yet. Take a look at the steps marked in red and try again.',
        'sort.item': 'Item',
        'sort.position': '{item}: position {i} of {n}',

        // Crossword
        'cw.across': 'Across',
        'cw.down': 'Down',
        'cw.dirAcross': 'across',
        'cw.dirDown': 'down',
        'cw.cell': '{num} {dir}, letter {i} of {n}',
        'cw.libError': 'The crossword library could not be loaded.',
        'cw.solved': 'Great! Crossword solved.',
        'cw.missing': 'Some letters are still missing.',
        'cw.wrongLetters': 'A few letters are still wrong (marked in red).',

        // Hotspot
        'hotspot.done': 'Great! You found all the safety issues.',
        'hotspot.gridLabel': 'Image areas to search: {rows} rows, {cols} columns',
        'hotspot.region': 'Image area row {r}, column {c}',
        'hotspot.hit': 'Correct: {label}. {progress}',
        'hotspot.miss': 'Nothing to find in row {r}, column {c}.',

        // Word search
        'ws.hint': 'Hint',
        'ws.libError': 'The word search library could not be loaded.',
        'ws.createError': 'The puzzle could not be created.',
        'ws.cell': '{letter}, row {r}, column {c}',
        'ws.gridLabel': 'Letter grid. Move with the arrow keys, Enter sets the start and end of a word, Escape cancels.',
        'ws.done': 'Great! You found all the words.',
        'ws.cancelled': 'Selection cancelled',
        'ws.anchorSet': 'Start set at {letter}. Now go to the last letter and confirm again.',
        'ws.straightOnly': 'Only straight lines are possible: horizontal, vertical or diagonal.',
        'ws.wordFound': '{word} found. {n} of {total} words.',
        'ws.wordWrong': '{word} is not one of the words you are looking for.',

        // Memory
        'memory.reshuffle': 'Shuffle again',
        'memory.pairs': '{n} / {total} pairs',
        'memory.done': 'Great! You found all the pairs.',
        'memory.image': 'Image',
        'memory.card': 'Card {i} of {n}',
        'memory.cardHidden': '{pos}, face down',
        'memory.cardOpen': '{pos}, face up: {name}',
        'memory.cardMatched': '{pos}, {name}, pair found',
        'memory.turned': 'Turned over: {names}',
        'memory.noPair': '. Not a pair. Both cards will be turned face down on your next move.',
        'memory.pairsFound': '{n} of {total} pairs found',

        // Building info
        'building.imageAlt': '{title} – image {i} of {n}',
        'carousel.prev': 'Previous image',
        'carousel.next': 'Next image',
        'carousel.goto': 'Image {i} of {n}',
        'carousel.pause': 'Pause slideshow',
        'carousel.play': 'Resume slideshow',

        // Badges
        'badges.quizzes': '{n}/{total} quizzes',
        'badges.achieved': 'Unlocked!',
        'badges.remainingOne': '1 more quiz to go!',
        'badges.remainingMany': '{n} more quizzes to go!',
        'badges.earned': 'Badge earned:',
        'badges.closeNotification': 'Close notification',

        // Map (screen reader)
        'map.containerLabel': 'Interactive campus map of TH Lübeck',
        'map.svgLabel': 'Campus map with buildings, quizzes and service points',
        'map.group.buildings': 'Buildings',
        'map.group.cafes': 'Cafés and kiosks',
        'map.group.bikes': 'Bike stations',
        'map.group.bus': 'Bus stops',
        'map.group.links': 'Further links',
        'map.group.quizzes': 'Quizzes',
        'map.type.building': 'Building',
        'map.type.cafe': 'Café',
        'map.type.bike': 'Bike station',
        'map.type.bus': 'Bus stop',
        'map.type.quiz': 'Quiz',
        'map.type.link': 'Link',
        'map.towards': 'towards {place}',
        'map.solved': ' – already solved',
        'map.newWindow': '(opens in a new window)',
        'map.logo': 'TH Lübeck website',
        'map.btn.Button_Studium': 'Degree programmes at TH Lübeck',
        'map.btn.Button_Speiseplan': 'Mensa menu',
        'map.btn.Button_Erkundungstour': 'Campus tour: film about TH Lübeck',
        'map.btn.Button_Hochschulsport': 'University sports Lübeck',
        'map.btn.Button_FabLab': 'FabLab Lübeck',
        'map.btn.Button_Innenstadt': 'Lübeck old town',
        'map.controls': 'Map view',
        'map.zoomIn': 'Zoom in',
        'map.zoomOut': 'Zoom out',

        // Announcements
        'announce.mapElements': 'Map elements',
        'announce.shown': '{name} shown',
        'announce.hidden': '{name} hidden',
        'announce.animOn': 'Animations on',
        'announce.animOff': 'Animations off',
        'announce.allShown': 'All map elements shown',
        'announce.allHidden': 'All map elements hidden'
    }
};

// Uebersetzung holen; {name}-Platzhalter werden durch vars ersetzt.
// Fehlt ein englischer Text, wird der deutsche verwendet.
function t(key, vars) {
    const table = UI_STRINGS[CURRENT_LANG] || UI_STRINGS[DEFAULT_LANG];
    let str = table[key];
    if (str === undefined) str = UI_STRINGS[DEFAULT_LANG][key];
    if (str === undefined) return key;
    if (vars) {
        str = str.replace(/\{(\w+)\}/g, (m, name) => (name in vars ? vars[name] : m));
    }
    return str;
}

// Statische Texte im DOM uebersetzen:
//   data-i18n="key"             -> textContent
//   data-i18n-html="key"        -> innerHTML
//   data-i18n-title="key"       -> title
//   data-i18n-aria-label="key"  -> aria-label
//   data-i18n-placeholder="key" -> placeholder
function applyStaticTranslations(root = document) {
    root.querySelectorAll('[data-i18n]').forEach(el => {
        el.textContent = t(el.dataset.i18n);
    });
    root.querySelectorAll('[data-i18n-html]').forEach(el => {
        el.innerHTML = t(el.dataset.i18nHtml);
    });
    root.querySelectorAll('[data-i18n-title]').forEach(el => {
        el.title = t(el.dataset.i18nTitle);
    });
    root.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
        el.placeholder = t(el.dataset.i18nPlaceholder);
    });
    root.querySelectorAll('[data-i18n-aria-label]').forEach(el => {
        el.setAttribute('aria-label', t(el.dataset.i18nAriaLabel));
    });
}

// Texte in der Campus-Karte (SVG) uebersetzen. Die Karte ist auf Deutsch;
// uebersetzbare Elemente tragen die Fremdsprache direkt im SVG:
//   data-en="…"             -> textContent (nur an Blattelementen: text, tspan, title)
//   data-en-aria-label="…"  -> aria-label
function localizeMapTexts(root) {
    if (!root || CURRENT_LANG === DEFAULT_LANG) return;
    const attr = `data-${CURRENT_LANG}`;
    root.querySelectorAll(`[${attr}]`).forEach(el => {
        el.textContent = el.getAttribute(attr);
    });
    root.querySelectorAll(`[${attr}-aria-label]`).forEach(el => {
        el.setAttribute('aria-label', el.getAttribute(`${attr}-aria-label`));
    });
    // Button-Titel sind im SVG als Pfade gezeichnet: Pfad-Gruppe aus-, Text einblenden
    root.querySelectorAll(`[${attr}-hide]`).forEach(el => { el.style.display = 'none'; });
    root.querySelectorAll(`[${attr}-show]`).forEach(el => { el.style.display = ''; });
    root.querySelectorAll(`[${attr}-width]`).forEach(el => {
        el.setAttribute('width', el.getAttribute(`${attr}-width`));
    });
}

function setLanguage(lang) {
    if (!SUPPORTED_LANGS.includes(lang) || lang === CURRENT_LANG) return;
    try {
        localStorage.setItem(LANG_STORAGE_KEY, lang);
        sessionStorage.setItem(LANG_SWITCH_FLAG, '1');
    } catch (e) {
    }
    // Ein ?lang= in der URL wuerde die neue Auswahl ueberstimmen
    const url = new URL(window.location.href);
    if (url.searchParams.has('lang')) {
        url.searchParams.set('lang', lang);
        window.location.replace(url.toString());
    } else {
        window.location.reload();
    }
}

function initLanguageSwitch() {
    document.querySelectorAll('[data-lang-option]').forEach(btn => {
        const lang = btn.dataset.langOption;
        const active = lang === CURRENT_LANG;
        btn.classList.toggle('active', active);
        btn.setAttribute('aria-pressed', active ? 'true' : 'false');
        btn.addEventListener('click', () => setLanguage(lang));
    });
}

// --- Inhalts-Overlay ---

function isPlainObject(v) {
    return v !== null && typeof v === 'object' && !Array.isArray(v);
}

// Ueberschreibt Felder in target mit denen aus overlay.
// Arrays werden elementweise (per Index) zusammengefuehrt.
function deepMergeInto(target, overlay) {
    Object.keys(overlay).forEach(key => {
        const src = overlay[key];
        const dst = target[key];
        if (Array.isArray(src) && Array.isArray(dst)) {
            src.forEach((item, i) => {
                if (item === undefined || item === null) return;
                if (isPlainObject(item) && isPlainObject(dst[i])) {
                    deepMergeInto(dst[i], item);
                } else {
                    dst[i] = item;
                }
            });
        } else if (isPlainObject(src) && isPlainObject(dst)) {
            deepMergeInto(dst, src);
        } else {
            target[key] = src;
        }
    });
}

// Wendet ein Overlay auf eine Liste von Objekten mit id an
function mergeById(list, overlayById) {
    if (!Array.isArray(list) || !overlayById) return;
    list.forEach(item => {
        const overlay = overlayById[item.id];
        if (overlay) deepMergeInto(item, overlay);
    });
}

// overlay = { quizModals: {id: {...}}, campusBuildings: {id: {...}},
//             badges: {id: {...}}, filters: [ {...}, ... ] }
function applyContentOverlay(lang, overlay) {
    if (lang !== CURRENT_LANG || !overlay) return;
    mergeById(quizModals, overlay.quizModals);
    mergeById(campusBuildings, overlay.campusBuildings);
    mergeById(ALL_BADGES, overlay.badges);
    if (Array.isArray(overlay.filters)) {
        overlay.filters.forEach((f, i) => {
            if (f && filters[i]) deepMergeInto(filters[i], f);
        });
    }
}

// i18n.js steht am Ende von <body>: Das statische Markup ist schon da und
// wird hier vor dem ersten Zeichnen uebersetzt (kein Aufblitzen von Deutsch).
document.title = t('page.title');
applyStaticTranslations();
initLanguageSwitch();

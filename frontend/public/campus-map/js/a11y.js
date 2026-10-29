/**
 * Accessibility (WCAG 2.1 AA).
 *
 * Adds what pure mouse/touch use lacks to the map and quizzes:
 *   - keyboard operation and names for the interactive SVG elements (2.1.1, 4.1.2)
 *   - zoom buttons as alternative to wheel and pinch (2.5.1)
 *   - live regions so status messages are announced (4.1.3)
 *
 * Loaded after main.js and triggered from there.
 */

// ============================================================
// Names for map elements
// ============================================================

/** Labels of the quick-access buttons on the map; this order is also the tab order of the links. */
const MAP_BUTTON_LABELS = {
    Button_Studium: t('map.btn.Button_Studium'),
    Button_Speiseplan: t('map.btn.Button_Speiseplan'),
    Button_Erkundungstour: t('map.btn.Button_Erkundungstour'),
    Button_Hochschulsport: t('map.btn.Button_Hochschulsport'),
    Button_FabLab: t('map.btn.Button_FabLab'),
    Button_Innenstadt: t('map.btn.Button_Innenstadt')
};

/** Two bus-stop pairs share a title in config.js (one per direction), so the direction from the ID is appended for screen readers. */
const BUS_RICHTUNG = {
    Bus_Bessemer_Straße_Sereetz: t('map.towards', { place: 'Sereetz' }),
    Bus_Bessemer_Straße_Bornkamp: t('map.towards', { place: 'Bornkamp' }),
    Bus_Technische_Hochschule_Sereetz: t('map.towards', { place: 'Sereetz' }),
    Bus_Technische_Hochschule_Grillenweg: t('map.towards', { place: 'Grillenweg' })
};

/** Display names of element types; the keys (meta.art) stay German because sorting and roles depend on them. */
const MAP_ART_LABELS = {
    'Gebäude': t('map.type.building'),
    'Café': t('map.type.cafe'),
    'Fahrradstation': t('map.type.bike'),
    'Bushaltestelle': t('map.type.bus'),
    'Quiz': t('map.type.quiz'),
    'Link': t('map.type.link')
};

/** Map element ID -> quiz ID (same mapping as in colorQuizElements). */
const MAP_QUIZ_IDS = {
    'Frage': 'Frage', 'Frage-2': 'Frage2', 'Frage-3': 'Frage3',
    'Frage-4': 'Frage4', 'Frage-5': 'Frage5', 'Frage-6': 'Frage6',
    'Frage-7': 'Frage7', 'Frage-8': 'Frage8', 'Frage-9': 'Frage9',
    'Frage-10': 'Frage10'
};

/**
 * Builds the index of all operable map elements.
 *
 * Only elements that actually trigger something: building passages are in CLICKABLE_Geb_CONFIG
 * but have no campusBuildings entry, so they would just be empty tab stops.
 *
 * @returns {Map<string, {name: string, art: string, neuesFenster: boolean}>}
 */
function buildMapLabelIndex() {
    const index = new Map();

    campusBuildings.forEach(b => {
        if (!b.id || !b.title) return;
        let art = 'Gebäude';
        if (b.id.startsWith('Kaffee_')) art = 'Café';
        else if (b.id.startsWith('Fahrradstation')) art = 'Fahrradstation';
        else if (b.id.startsWith('Bus_')) art = 'Bushaltestelle';
        let name = b.title.replace(/Gebaeude/g, 'Gebäude');
        if (BUS_RICHTUNG[b.id]) name += ` (${BUS_RICHTUNG[b.id]})`;
        index.set(b.id, { name, art, neuesFenster: false });
    });

    Object.keys(MAP_QUIZ_IDS).forEach(mapId => {
        const quiz = quizModals.find(q => q.id === MAP_QUIZ_IDS[mapId]);
        if (!quiz) return;
        index.set(mapId, {
            name: quiz.content && quiz.content.question ? `${quiz.title}: ${quiz.content.question}` : quiz.title,
            art: 'Quiz',
            neuesFenster: false
        });
    });

    Object.keys(MAP_BUTTON_LABELS).forEach(id => {
        index.set(id, { name: MAP_BUTTON_LABELS[id], art: 'Link', neuesFenster: true });
    });

    index.set('Logo', { name: t('map.logo'), art: 'Link', neuesFenster: true });

    return index;
}

/** Builds the full name of a map element; screen readers announce role="button" themselves, so the name carries the type (building, café, …) instead. */
function mapElementLabel(id, meta) {
    if (meta.art === 'Quiz') {
        const geloest = typeof getCompletedQuizIds === 'function'
            && getCompletedQuizIds().includes(MAP_QUIZ_IDS[id]);
        return `${meta.name}${geloest ? t('map.solved') : ''}`;
    }
    if (meta.art === 'Link') {
        return `${meta.name} ${t('map.newWindow')}`;
    }
    // "Gebäude E.5" instead of "Gebäude: Gebäude E.5"
    const art = MAP_ART_LABELS[meta.art] || meta.art;
    if (meta.name.startsWith(art)) return meta.name;
    return `${art}: ${meta.name}`;
}

// ============================================================
// Tab order on the map (2.4.3)
// ============================================================
//
// SVG elements sit in drawing order, which makes Tab jump across the map; the DOM
// cannot be reordered (order decides what is drawn on top). Therefore:
//   - only the first map element is reachable by Tab (tabindex 0), all others have tabindex -1,
//   - Tab / Shift+Tab inside the map follow MAP_TAB_ORDER,
//   - at the start or end the focus leaves the map normally.

/** Group order when tabbing through. */
const MAP_GRUPPEN_REIHENFOLGE = ['Gebäude', 'Quiz', 'Café', 'Fahrradstation', 'Bushaltestelle', 'Link'];

/** Sort key within a group: buildings by campus area (A–G) and number (A.1, B.59, B.60 … G.3), those without an area code (MFC, GründerCube) last. */
function mapSortKey(id, meta) {
    if (meta.art === 'Gebäude') {
        const m = id.match(/_([A-G])_(\d+)([a-z]?)$/);
        if (m) return `0 ${m[1]} ${m[2].padStart(3, '0')} ${m[3]}`;
        return `1 ${meta.name}`;
    }
    if (meta.art === 'Quiz') {
        const nr = id === 'Frage' ? 1 : parseInt(id.split('-')[1], 10);
        return String(nr).padStart(3, '0');
    }
    if (meta.art === 'Link') {
        // Order from MAP_BUTTON_LABELS, the logo last
        const pos = Object.keys(MAP_BUTTON_LABELS).indexOf(id);
        return String(pos < 0 ? 999 : pos).padStart(3, '0');
    }
    return meta.name;
}

/** IDs of all map elements in tab order. */
let mapTabOrder = [];

function buildMapTabOrder(index) {
    return [...index.entries()]
        .sort(([idA, a], [idB, b]) => {
            const g = MAP_GRUPPEN_REIHENFOLGE.indexOf(a.art) - MAP_GRUPPEN_REIHENFOLGE.indexOf(b.art);
            if (g !== 0) return g;
            return mapSortKey(idA, a).localeCompare(mapSortKey(idB, b), CURRENT_LANG, { numeric: true });
        })
        .map(([id]) => id);
}

/** The currently operable (visible) map elements in tab order. */
function mapTabElements() {
    const svg = document.querySelector('#lottieMap svg');
    if (!svg) return [];
    return mapTabOrder
        .map(id => svg.querySelector(`[data-a11y-id="${CSS.escape(id)}"]`))
        .filter(el => el && el.dataset.a11ySichtbar === 'true');
}

/** Only the first operable element stays a regular tab stop. */
function updateMapTabStops() {
    const elemente = mapTabElements();
    document.querySelectorAll('#lottieMap [data-a11y-id]').forEach(el => el.setAttribute('tabindex', '-1'));
    if (elemente.length) elemente[0].setAttribute('tabindex', '0');
}

function handleMapTab(e) {
    if (e.key !== 'Tab' || e.altKey || e.ctrlKey || e.metaKey) return;
    const aktuell = e.target.closest && e.target.closest('[data-a11y-id]');
    if (!aktuell) return;

    const elemente = mapTabElements();
    const pos = elemente.indexOf(aktuell);
    const ziel = elemente[pos + (e.shiftKey ? -1 : 1)];

    if (pos >= 0 && ziel) {
        e.preventDefault();
        ziel.focus();
        return;
    }

    // Map edge reached: let the browser tab on normally, but it must not land on the entry element (tabindex 0) somewhere mid-DOM, so remove it briefly.
    const einstieg = elemente[0];
    if (einstieg && einstieg !== aktuell) {
        einstieg.setAttribute('tabindex', '-1');
        window.setTimeout(() => einstieg.setAttribute('tabindex', '0'), 0);
    }
    if (e.shiftKey && pos === 0) {
        // Backwards from the very first: before the map, i.e. the last zoom button
        const zoom = document.querySelectorAll('.map-controls button');
        if (zoom.length) {
            e.preventDefault();
            zoom[zoom.length - 1].focus();
        }
    }
}

/** Keeps the focused element in view; when zoomed in, focus could otherwise land outside the image (2.4.7). */
function keepMapFocusInView(e) {
    const el = e.target.closest && e.target.closest('[data-a11y-id]');
    if (el && window.mapZoomControls && window.mapZoomControls.panToElement) {
        window.mapZoomControls.panToElement(el);
    }
}

// Safari draws no outline around SVG elements, so the focus ring is an HTML box laid over the map.
let fokusRahmen = null;

function zeigeKartenFokus(e) {
    const el = e.target.closest && e.target.closest('[data-a11y-id]');
    const container = document.getElementById('mapContainer');
    if (!el || !container || !el.matches(':focus-visible')) return;
    if (!fokusRahmen) {
        fokusRahmen = document.createElement('div');
        fokusRahmen.className = 'map-focus-ring';
        fokusRahmen.setAttribute('aria-hidden', 'true');
    }
    container.appendChild(fokusRahmen);
    fokusRahmen.dataset.ziel = el.dataset.a11yId;
    const folgen = () => {
        if (fokusRahmen.dataset.ziel !== el.dataset.a11yId) return;
        if (document.activeElement !== el) {
            fokusRahmen.remove();
            delete fokusRahmen.dataset.ziel;
            return;
        }
        const r = el.getBoundingClientRect();
        const c = container.getBoundingClientRect();
        Object.assign(fokusRahmen.style, {
            left: `${r.left - c.left}px`,
            top: `${r.top - c.top}px`,
            width: `${r.width}px`,
            height: `${r.height}px`
        });
        window.requestAnimationFrame(folgen);
    };
    folgen();
}

// ============================================================
// Keyboard and ARIA layer on the map
// ============================================================

let mapLabelIndex = null;

/** Makes the interactive SVG groups focusable, names them and wires Enter/Space to the click action; called once the map SVG is in the DOM. */
function setupMapAccessibility() {
    const svg = document.querySelector('#lottieMap svg');
    if (!svg) return;

    mapLabelIndex = buildMapLabelIndex();

    // The map as a named region, otherwise it is nameless in screen readers.
    const container = document.getElementById('mapContainer');
    if (container) {
        container.setAttribute('aria-label', t('map.containerLabel'));
    }
    // Deliberately no <title> in the SVG: browsers show it as a hover tooltip over the whole map, aria-label alone names it.
    svg.setAttribute('role', 'group');
    svg.setAttribute('aria-label', t('map.svgLabel'));
    // Otherwise Chrome makes the SVG itself a tab stop as a scrollable area, an empty stop between zoom buttons and first building.
    svg.setAttribute('tabindex', '-1');

    // Name the groups so the elements appear sorted in screen readers
    const gruppenNamen = {
        Gebaeude: t('map.group.buildings'),
        Kaffee: t('map.group.cafes'),
        Fahrradstationen: t('map.group.bikes'),
        Bushaltestellen: t('map.group.bus'),
        Buttons: t('map.group.links'),
        Studierende_mit_Fragen: t('map.group.quizzes')
    };
    Object.keys(gruppenNamen).forEach(id => {
        const g = svg.querySelector(`g#${CSS.escape(id)}`);
        if (g) {
            g.setAttribute('role', 'group');
            g.setAttribute('aria-label', gruppenNamen[id]);
        }
    });

    mapLabelIndex.forEach((meta, id) => {
        const el = svg.querySelector(`#${CSS.escape(id)}`);
        if (!el) return;
        // Links open a website and are announced as links
        el.setAttribute('role', meta.art === 'Link' ? 'link' : 'button');
        el.setAttribute('tabindex', '-1');
        el.setAttribute('aria-label', mapElementLabel(id, meta));
        el.dataset.a11yId = id;
    });

    mapTabOrder = buildMapTabOrder(mapLabelIndex);
    svg.addEventListener('keydown', handleMapTab);
    svg.addEventListener('focusin', keepMapFocusInView);
    svg.addEventListener('focusin', zeigeKartenFokus);

    // Enter and Space trigger the same action as a click.
    svg.addEventListener('keydown', e => {
        if (e.key !== 'Enter' && e.key !== ' ' && e.key !== 'Spacebar') return;
        const ziel = e.target.closest('[data-a11y-id]');
        if (!ziel) return;
        e.preventDefault();
        e.stopPropagation();
        activateMapTarget(ziel);
    });

    // Escape on the map ends keyboard selection: focus goes to the map area itself (no ring), the next Tab starts at the zoom buttons again.
    if (container && !container._a11yEscape) {
        container._a11yEscape = e => {
            if (e.key !== 'Escape' || e.target === container) return;
            e.preventDefault();
            container.focus();
        };
        container.addEventListener('keydown', container._a11yEscape);
    }

    syncMapA11yState();
}

/** Keeps focusability and names current; hidden map elements (settings -> map elements) have display:none children and would remain invisible focus stops. */
function syncMapA11yState() {
    const svg = document.querySelector('#lottieMap svg');
    if (!svg || !mapLabelIndex) return;

    mapLabelIndex.forEach((meta, id) => {
        const el = svg.querySelector(`#${CSS.escape(id)}`);
        if (!el) return;
        const box = el.getBoundingClientRect();
        const sichtbar = box.width > 0 && box.height > 0;
        el.dataset.a11ySichtbar = sichtbar ? 'true' : 'false';
        if (sichtbar) {
            el.removeAttribute('aria-hidden');
            el.setAttribute('aria-label', mapElementLabel(id, meta));
        } else {
            el.setAttribute('aria-hidden', 'true');
        }
    });

    updateMapTabStops();
}

// ============================================================
// Zoom buttons (2.5.1: alternative to wheel and pinch)
// ============================================================

/** Builds the zoom controls into the map container. */
function setupMapZoomControls() {
    const container = document.getElementById('mapContainer');
    if (!container || container.querySelector('.map-controls')) return;

    const gruppe = document.createElement('div');
    gruppe.className = 'map-controls';
    gruppe.setAttribute('role', 'group');
    gruppe.setAttribute('aria-label', t('map.controls'));
    gruppe.innerHTML = `
        <button type="button" class="map-zoom-btn" data-map-search aria-label="${t('legend.searchLabel')}" title="${t('legend.searchButtonTitle')}" aria-keyshortcuts="Space">
            <i class="fas fa-search" aria-hidden="true"></i>
        </button>
        <button type="button" class="map-zoom-btn" data-zoom="in" aria-label="${t('map.zoomIn')}">
            <i class="fas fa-plus" aria-hidden="true"></i>
        </button>
        <button type="button" class="map-zoom-btn" data-zoom="out" aria-label="${t('map.zoomOut')}">
            <i class="fas fa-minus" aria-hidden="true"></i>
        </button>`;
    // Before the map in the DOM, so the zoom buttons follow the header in tab order instead of all map elements; CSS handles the screen position.
    container.insertBefore(gruppe, container.firstChild);

    gruppe.addEventListener('click', e => {
        if (e.target.closest('[data-map-search]')) {
            if (typeof campusLegend !== 'undefined') campusLegend.openSearch();
            return;
        }
        const btn = e.target.closest('[data-zoom]');
        if (!btn || !window.mapZoomControls) return;
        if (btn.dataset.zoom === 'in') window.mapZoomControls.zoomIn();
        else window.mapZoomControls.zoomOut();
        announce(window.mapZoomControls.zoomText());
        syncMapA11yState();
    });
}

// ============================================================
// Status messages (4.1.3)
// ============================================================

/** Announces a status message via the live region; clearing it briefly forces the announcement even for a repeated text. */
function announce(text) {
    const region = document.getElementById('a11yLive');
    if (!region || !text) return;
    region.textContent = '';
    window.setTimeout(() => { region.textContent = text; }, 60);
}

window.setupMapAccessibility = setupMapAccessibility;
window.syncMapA11yState = syncMapA11yState;
window.setupMapZoomControls = setupMapZoomControls;
window.announce = announce;

// ============================================================
// Wiring with main.js
// ============================================================
//
// main.js calls these functions in several places; wrapping the functions once keeps the accessibility logic in one place.

/** setupZoomPan() runs once the map SVG is in the DOM. */
if (typeof window.setupZoomPan === 'function') {
    const zoomPanBasis = window.setupZoomPan;
    window.setupZoomPan = function () {
        const ergebnis = zoomPanBasis.apply(this, arguments);
        setupMapAccessibility();
        setupMapZoomControls();
        return ergebnis;
    };
}

/** Showing or hiding map elements changes what may be focusable. */
if (typeof window.updateFilterStyles === 'function') {
    const filterBasis = window.updateFilterStyles;
    window.updateFilterStyles = function () {
        const ergebnis = filterBasis.apply(this, arguments);
        syncMapA11yState();
        return ergebnis;
    };
}

/** Solved quizzes get an "already solved" suffix in their name. */
if (typeof window.colorQuizElements === 'function') {
    const quizFarbenBasis = window.colorQuizElements;
    window.colorQuizElements = function () {
        const ergebnis = quizFarbenBasis.apply(this, arguments);
        syncMapA11yState();
        return ergebnis;
    };
}

// ============================================================
// Quiz types that natively only support mouse/touch
// ============================================================

/** Memory: cards are <button> and operable by themselves; this reads out the state (hidden, flipped, matched) and removes matched pairs from the tab path. */
function enhanceMemoryQuiz(container) {
    const grid = container.querySelector('.memory-grid');
    if (!grid) return;

    const aktualisiere = () => {
        const karten = [...grid.querySelectorAll('.memory-card')];
        karten.forEach((k, i) => {
            const name = k.dataset.cardLabel || t('memory.image');
            const pos = t('memory.card', { i: i + 1, n: karten.length });
            if (k.classList.contains('matched')) {
                k.setAttribute('aria-label', t('memory.cardMatched', { pos, name }));
                k.disabled = true;
            } else if (k.classList.contains('flipped')) {
                k.setAttribute('aria-label', t('memory.cardOpen', { pos, name }));
                k.disabled = false;
            } else {
                k.setAttribute('aria-label', t('memory.cardHidden', { pos }));
                k.disabled = false;
            }
        });
    };

    aktualisiere();

    // Classes are set in several places and partly delayed (flip animation); an observer catches all paths.
    if (grid._a11yObserver) grid._a11yObserver.disconnect();
    let letzterStand = -1;
    let aufgedeckt = new Set();
    grid._a11yObserver = new MutationObserver(() => {
        aktualisiere();

        // Focus stays on the card when flipping; screen readers do not reliably read the name change, so announce it.
        const offen = new Set([...grid.querySelectorAll('.memory-card.flipped:not(.matched)')]);
        const neu = [...offen].filter(k => !aufgedeckt.has(k));
        aufgedeckt = offen;
        if (neu.length) {
            let text = t('memory.turned', { names: neu.map(k => k.dataset.cardLabel || t('memory.image')).join(', ') });
            // No pair: both cards stay open until the next card is flipped (as main.js does it).
            const [a, b] = [...offen];
            if (offen.size === 2 && a.dataset.pairId !== b.dataset.pairId) {
                text += t('memory.noPair');
            }
            announce(text);
        }

        const paare = grid.querySelectorAll('.memory-card.matched').length / 2;
        if (paare !== letzterStand) {
            letzterStand = paare;
            const gesamt = grid.querySelectorAll('.memory-card').length / 2;
            if (paare > 0) announce(t('memory.pairsFound', { n: paare, total: gesamt }));
        }
    });
    grid._a11yObserver.observe(grid, { attributes: true, attributeFilter: ['class'], subtree: true });
}

/**
 * Word search: replaces the drag gesture with anchor + cursor.
 *
 * Arrow keys move the cursor, Enter sets the first letter, a second Enter confirms the word, Escape cancels.
 * Unlike mouse dragging only an exactly straight line counts, which is more predictable on a keyboard.
 */
function enhanceWordSearch(container) {
    const grid = container.querySelector('.wordsearch-grid');
    if (!grid) return;
    const alle = [...grid.querySelectorAll('.wordsearch-cell')];
    if (!alle.length) return;

    const zelle = (r, c) => grid.querySelector(`.wordsearch-cell[data-row="${r}"][data-col="${c}"]`);
    const maxR = Math.max(...alle.map(z => +z.dataset.row));
    const maxC = Math.max(...alle.map(z => +z.dataset.col));

    let cursor = { r: 0, c: 0 };
    let anker = null;

    const linie = () => {
        if (!anker) return [];
        const dr = cursor.r - anker.r, dc = cursor.c - anker.c;
        if (!(dr === 0 || dc === 0 || Math.abs(dr) === Math.abs(dc))) return [];
        const schritte = Math.max(Math.abs(dr), Math.abs(dc));
        const sr = Math.sign(dr), sc = Math.sign(dc);
        const liste = [];
        for (let i = 0; i <= schritte; i++) {
            const z = zelle(anker.r + i * sr, anker.c + i * sc);
            if (z) liste.push(z);
        }
        return liste;
    };

    const zeichne = () => {
        grid.querySelectorAll('.wordsearch-cell.highlight').forEach(z => z.classList.remove('highlight'));
        linie().forEach(z => z.classList.add('highlight'));
    };

    const setzeCursor = (r, c, fokussieren) => {
        cursor = { r: Math.max(0, Math.min(maxR, r)), c: Math.max(0, Math.min(maxC, c)) };
        alle.forEach(z => z.setAttribute('tabindex', '-1'));
        const z = zelle(cursor.r, cursor.c);
        if (z) {
            z.setAttribute('tabindex', '0');
            if (fokussieren) z.focus();
        }
        zeichne();
    };

    const ankerLoesen = () => {
        anker = null;
        grid.querySelectorAll('.ws-anchor').forEach(z => z.classList.remove('ws-anchor'));
        zeichne();
    };

    setzeCursor(0, 0, false);

    if (grid._a11yKeys) grid.removeEventListener('keydown', grid._a11yKeys);
    grid._a11yKeys = (e) => {
        const richtungen = {
            ArrowUp: [-1, 0], ArrowDown: [1, 0], ArrowLeft: [0, -1], ArrowRight: [0, 1]
        };
        if (richtungen[e.key]) {
            e.preventDefault();
            setzeCursor(cursor.r + richtungen[e.key][0], cursor.c + richtungen[e.key][1], true);
            return;
        }
        if (e.key === 'Home') { e.preventDefault(); setzeCursor(cursor.r, 0, true); return; }
        if (e.key === 'End') { e.preventDefault(); setzeCursor(cursor.r, maxC, true); return; }
        if (e.key === 'Escape' && anker) { e.preventDefault(); ankerLoesen(); announce(t('ws.cancelled')); return; }
        if (e.key !== 'Enter' && e.key !== ' ') return;

        e.preventDefault();
        const aktuelle = zelle(cursor.r, cursor.c);
        if (!anker) {
            anker = { r: cursor.r, c: cursor.c };
            if (aktuelle) aktuelle.classList.add('ws-anchor');
            announce(t('ws.anchorSet', { letter: aktuelle ? aktuelle.textContent : '' }));
            return;
        }
        const auswahl = linie();
        if (auswahl.length < 2) {
            announce(t('ws.straightOnly'));
            return;
        }
        const vorher = container._wsFoundCount || 0;
        checkWordSearchSelection(container, auswahl);
        const nachher = container._wsFoundCount || 0;
        const wort = auswahl.map(z => z.textContent).join('');
        announce(nachher > vorher
            ? t('ws.wordFound', { word: wort, n: nachher, total: container._wsTotal })
            : t('ws.wordWrong', { word: wort }));
        ankerLoesen();
        setzeCursor(cursor.r, cursor.c, true);
    };
    grid.addEventListener('keydown', grid._a11yKeys);
}

/**
 * Image hotspot: lays an invisible grid of focusable regions over the image.
 *
 * Regions carry neutral names ("row 2, column 3"); the hotspot text would give the puzzle away to screen reader users.
 * pointer-events:none in the CSS keeps mouse clicks pixel-exact on the overlay instead of rounding to grid cells.
 */
function enhanceHotspotQuiz(container) {
    const overlay = container.querySelector('.hotspot-overlay');
    if (!overlay || overlay.querySelector('.hotspot-keyboard-grid')) return;

    const quiz = quizModals.find(q => q.id === container.dataset.quizId);
    const hotspots = (quiz && quiz.content && quiz.content.hotspots) || [];
    if (!hotspots.length) return;

    const ZEILEN = 5, SPALTEN = 6;
    const raster = document.createElement('div');
    raster.className = 'hotspot-keyboard-grid';
    raster.setAttribute('role', 'group');
    raster.setAttribute('aria-label', t('hotspot.gridLabel', { rows: ZEILEN, cols: SPALTEN }));

    for (let r = 0; r < ZEILEN; r++) {
        for (let c = 0; c < SPALTEN; c++) {
            const b = document.createElement('button');
            b.type = 'button';
            b.className = 'hotspot-region';
            b.style.left = `${c * 100 / SPALTEN}%`;
            b.style.top = `${r * 100 / ZEILEN}%`;
            b.style.width = `${100 / SPALTEN}%`;
            b.style.height = `${100 / ZEILEN}%`;
            b.dataset.row = String(r);
            b.dataset.col = String(c);
            // Roving tabindex: one cell is the tab stop, the rest via arrow keys
            b.tabIndex = (r === 0 && c === 0) ? 0 : -1;
            b.setAttribute('aria-label', t('hotspot.region', { r: r + 1, c: c + 1 }));
            raster.appendChild(b);
        }
    }
    overlay.appendChild(raster);

    const felder = Array.from(raster.querySelectorAll('.hotspot-region'));
    const fokusAuf = (r, c) => {
        r = Math.max(0, Math.min(ZEILEN - 1, r));
        c = Math.max(0, Math.min(SPALTEN - 1, c));
        felder.forEach(f => f.tabIndex = -1);
        const ziel = felder[r * SPALTEN + c];
        ziel.tabIndex = 0;
        ziel.focus();
    };

    raster.addEventListener('keydown', e => {
        const feld = e.target.closest('.hotspot-region');
        if (!feld) return;
        const r = +feld.dataset.row, c = +feld.dataset.col;
        const ziele = {
            ArrowUp: [r - 1, c], ArrowDown: [r + 1, c],
            ArrowLeft: [r, c - 1], ArrowRight: [r, c + 1],
            Home: [r, 0], End: [r, SPALTEN - 1]
        };
        if (!ziele[e.key]) return;
        e.preventDefault();
        fokusAuf(...ziele[e.key]);
    });

    raster.addEventListener('click', e => {
        const feld = e.target.closest('.hotspot-region');
        if (!feld) return;
        // Otherwise the delegated overlay handler in main.js fires as well
        e.stopPropagation();

        const r = +feld.dataset.row, c = +feld.dataset.col;
        const x0 = c * 100 / SPALTEN, x1 = (c + 1) * 100 / SPALTEN;
        const y0 = r * 100 / ZEILEN, y1 = (r + 1) * 100 / ZEILEN;

        // Does a not yet found hotspot intersect this cell?
        const gefunden = container._hotspotFound || new Set();
        let treffer = null;
        hotspots.forEach((h, i) => {
            if (treffer || gefunden.has(i)) return;
            const nx = Math.max(x0, Math.min(x1, h.x));
            const ny = Math.max(y0, Math.min(y1, h.y));
            if (Math.hypot(h.x - nx, h.y - ny) <= h.radius) treffer = h;
        });

        // main.js still does the actual evaluation, same code for mouse and keyboard including markers and progress.
        const rect = overlay.getBoundingClientRect();
        const px = treffer ? treffer.x : (x0 + x1) / 2;
        const py = treffer ? treffer.y : (y0 + y1) / 2;
        handleHotspotClick(overlay, {
            clientX: rect.left + rect.width * px / 100,
            clientY: rect.top + rect.height * py / 100
        });

        const stand = container.querySelector('.hotspot-progress');
        announce(treffer
            ? t('hotspot.hit', { label: treffer.label, progress: stand ? stand.textContent : '' })
            : t('hotspot.miss', { r: r + 1, c: c + 1 }));
    });
}

// --- Hooking into the init functions from main.js ---

if (typeof window.initMemoryGame === 'function') {
    const basis = window.initMemoryGame;
    window.initMemoryGame = function (container) {
        const ergebnis = basis.apply(this, arguments);
        // initMemoryGame rebuilds with a delay when reshuffling (fade animation)
        window.setTimeout(() => enhanceMemoryQuiz(container), 320);
        return ergebnis;
    };
}

if (typeof window.initWordSearch === 'function') {
    const basis = window.initWordSearch;
    window.initWordSearch = function (container) {
        const ergebnis = basis.apply(this, arguments);
        enhanceWordSearch(container);
        return ergebnis;
    };
}

if (typeof window.initHotspotQuiz === 'function') {
    const basis = window.initHotspotQuiz;
    window.initHotspotQuiz = function (container) {
        const ergebnis = basis.apply(this, arguments);
        enhanceHotspotQuiz(container);
        return ergebnis;
    };
}

// ============================================================
// Focus management on open and close (2.4.3)
// ============================================================
//
// Bootstrap returns focus to the data-bs-toggle element that opened the panel, but map elements open
// programmatically, so focus would fall to <body> and keyboard users would restart tabbing; we remember the opener ourselves.

let letzterKartenFokus = null;

// Was the last input keyboard or mouse/touch? After a mouse click the map element should get no focus ring on close.
let letzteEingabeTastatur = false;
document.addEventListener('keydown', e => {
    if (!['Shift', 'Control', 'Alt', 'Meta'].includes(e.key)) letzteEingabeTastatur = true;
}, true);
document.addEventListener('pointerdown', () => { letzteEingabeTastatur = false; }, true);

if (typeof window.activateMapTarget === 'function') {
    const aktivierenBasis = window.activateMapTarget;
    window.activateMapTarget = function (target) {
        letzterKartenFokus = target && target.closest ? target.closest('[data-a11y-id]') : null;
        return aktivierenBasis.apply(this, arguments);
    };
}

function fokusZurueckGeben() {
    const ziel = letzterKartenFokus;
    letzterKartenFokus = null;
    if (!letzteEingabeTastatur) return;
    if (!ziel || !document.contains(ziel)) return;
    // Return focus only if the element is still operable; it may have been hidden via settings meanwhile.
    if (ziel.dataset.a11ySichtbar !== 'true') return;
    ziel.focus();
}

document.addEventListener('hidden.bs.offcanvas', fokusZurueckGeben);

// The badges panel opens via JavaScript, Bootstrap does not know the trigger, so focus would land on <body> after closing.
document.addEventListener('hidden.bs.offcanvas', e => {
    if (e.target.id !== 'badgesOffcanvas') return;
    // At event time the focus is often still inside the panel just hidden
    const a = document.activeElement;
    if (!a || a === document.body || e.target.contains(a)) {
        const btn = document.getElementById('toolboxBadgesBtn');
        if (btn) btn.focus();
    }
});

// On phones badges and settings sit in the collapsed menu; their button is invisible and cannot take focus, so the menu button gets it.
document.addEventListener('hidden.bs.offcanvas', e => {
    if (e.target.id !== 'badgesOffcanvas' && e.target.id !== 'filterOffcanvas') return;
    const a = document.activeElement;
    if (a && a !== document.body && !e.target.contains(a)) return;
    const menuBtn = document.getElementById('toolboxMenuBtn');
    if (menuBtn && menuBtn.offsetParent) menuBtn.focus();
});
document.addEventListener('hidden.bs.modal', fokusZurueckGeben);

// ============================================================
// Announce visibility changes (4.1.3)
// ============================================================
//
// Showing or hiding map elements changes the map without moving focus; without an announcement screen reader users miss it.

document.addEventListener('change', e => {
    const cb = e.target.closest && e.target.closest('#filterOptions input[type="checkbox"]');
    if (cb) {
        const karte = cb.closest('.filter-card');
        const name = karte && karte.querySelector('.filter-label-text')
            ? karte.querySelector('.filter-label-text').textContent.trim() : t('announce.mapElements');
        announce(t(cb.checked ? 'announce.shown' : 'announce.hidden', { name }));
        return;
    }
    if (e.target.id === 'animationsToggle') {
        announce(t(e.target.checked ? 'announce.animOn' : 'announce.animOff'));
    }
});

document.addEventListener('click', e => {
    if (!e.target.closest || !e.target.closest('#toggleAllBtn')) return;
    // The button state is only updated in the main.js handler
    window.setTimeout(() => {
        const btn = document.getElementById('toggleAllBtn');
        if (!btn) return;
        announce(btn.classList.contains('active')
            ? t('announce.allShown')
            : t('announce.allHidden'));
    }, 100);
});

// ============================================================
// Info button in the quiz modal (2.1.1, 4.1.2)
// ============================================================
//
// The trigger is a <div> whose click logic hangs on icon and close text (rebuilt on every toggle); instead of
// restructuring it, the container gets role, focus and name, and Enter/Space click the current icon.

function enhanceInfoTrigger(modal) {
    const trigger = modal.querySelector('.info-icon-trigger');
    const bereich = modal.querySelector('#campusInfosOverlay');
    if (!trigger || !bereich) return;

    trigger.setAttribute('role', 'button');
    trigger.setAttribute('tabindex', '0');
    trigger.setAttribute('aria-controls', 'campusInfosOverlay');

    const sync = () => {
        const offen = bereich.classList.contains('show');
        trigger.setAttribute('aria-expanded', offen ? 'true' : 'false');
        trigger.setAttribute('aria-label', t(offen ? 'quiz.infoHide' : 'quiz.infoShow'));
    };
    sync();

    if (bereich._a11yObserver) bereich._a11yObserver.disconnect();
    bereich._a11yObserver = new MutationObserver(sync);
    bereich._a11yObserver.observe(bereich, { attributes: true, attributeFilter: ['class'] });

    if (!trigger._a11yKeys) {
        trigger._a11yKeys = e => {
            if (e.key !== 'Enter' && e.key !== ' ') return;
            e.preventDefault();
            const ziel = trigger.querySelector('.fas.fa-info-circle, span');
            if (ziel) ziel.click();
        };
        trigger.addEventListener('keydown', trigger._a11yKeys);
    }
}

// After main.js: setupAccordionToggle clones the container on open, so enhance only afterwards (setTimeout).
document.addEventListener('shown.bs.modal', e => {
    window.setTimeout(() => enhanceInfoTrigger(e.target), 0);
});

// ============================================================
// Focus after "Check" / "Try again" (2.4.3)
// ============================================================
//
// main.js hides the pressed button (display:none), so focus falls to <body> and Escape no longer closes the modal
// (Bootstrap only listens with focus inside the dialog); the other, now visible button gets the focus.

document.addEventListener('click', e => {
    const btn = e.target.closest && e.target.closest('.quiz-submit-btn, .quiz-reset-btn');
    if (!btn) return;
    const aktionen = btn.closest('.quiz-actions');
    if (!aktionen) return;
    window.setTimeout(() => {
        const a = document.activeElement;
        if (a && a !== document.body && a.offsetParent !== null && !a.disabled) return;
        const ziel = [...aktionen.querySelectorAll('.quiz-reset-btn, .quiz-submit-btn')]
            .find(b => b.offsetParent !== null && !b.disabled);
        if (ziel) ziel.focus();
    }, 50);
});

// ============================================================
// Sort quiz: announce moves (4.1.3)
// ============================================================

document.addEventListener('click', e => {
    const pfeil = e.target.closest && e.target.closest('.sort-arrow-btn');
    if (!pfeil) return;
    const item = pfeil.closest('.sort-item');
    const liste = pfeil.closest('.sort-list');
    if (!item || !liste) return;
    window.setTimeout(() => {
        const alle = [...liste.querySelectorAll('.sort-item')];
        const text = item.querySelector('.sort-text');
        announce(t('sort.position', { item: text ? text.textContent.trim() : t('sort.item'), i: alle.indexOf(item) + 1, n: alle.length }));
    }, 30);
});

// ============================================================
// Quiz dialogs: question as description, answers as group (1.3.1)
// ============================================================
//
// Otherwise the screen reader only says "Quiz 3, dialog" on open and the answers are loose checkboxes unrelated to the question.

document.addEventListener('show.bs.modal', e => {
    const modal = e.target;
    const frage = modal.querySelector('.quiz-question');
    if (!frage) return;
    if (!frage.id) frage.id = `${modal.id}-frage`;
    modal.setAttribute('aria-describedby', frage.id);

    const optionen = modal.querySelector('.quiz-options, .quiz-image-grid');
    if (optionen) {
        const istRadio = !!optionen.querySelector('input[type="radio"]');
        optionen.setAttribute('role', istRadio ? 'radiogroup' : 'group');
        optionen.setAttribute('aria-labelledby', frage.id);
    }
});

// ============================================================
// Image carousel in the building info (2.2.2 pause, stop)
// ============================================================
//
// Images auto-advance every 3 seconds, so a pause control is needed; the carousel also stops while keyboard focus
// is inside it, and a manually chosen image is announced.

function enhanceBuildingCarousel() {
    const el = document.getElementById('carouselBuilding');
    if (!el || el.querySelector('.carousel-pause-btn') || typeof bootstrap === 'undefined') return;
    const inst = bootstrap.Carousel.getOrCreateInstance(el);

    let angehalten = false;   // by the user via button
    let fokusDrin = false;

    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'carousel-pause-btn';
    const zeichne = () => {
        btn.setAttribute('aria-label', t(angehalten ? 'carousel.play' : 'carousel.pause'));
        btn.innerHTML = `<i class="fas ${angehalten ? 'fa-play' : 'fa-pause'}" aria-hidden="true"></i>`;
    };
    const steuere = () => { if (angehalten || fokusDrin) inst.pause(); else inst.cycle(); };
    btn.addEventListener('click', () => {
        angehalten = !angehalten;
        zeichne();
        steuere();
    });
    zeichne();
    el.appendChild(btn);

    el.addEventListener('focusin', () => { fokusDrin = true; steuere(); });
    el.addEventListener('focusout', e => {
        if (el.contains(e.relatedTarget)) return;
        fokusDrin = false;
        steuere();
    });
    el.addEventListener('slid.bs.carousel', () => {
        if (!fokusDrin) return;
        const bild = el.querySelector('.carousel-item.active img');
        if (bild) announce(bild.alt);
    });
}

document.addEventListener('shown.bs.offcanvas', e => {
    if (e.target.id !== 'buildingInfoOffcanvas') return;
    // after main.js, which starts the carousel in the same event
    window.setTimeout(enhanceBuildingCarousel, 0);
});

// ============================================================
// Tab in Safari (2.1.1)
// ============================================================
//
// Safari skips buttons and links on Tab by default, an explicit tabindex puts them back in the order.

function tabStoppsSetzen(wurzel) {
    if (!wurzel.querySelectorAll) return;
    const auswahl = 'a[href]:not([tabindex]), button:not([tabindex])';
    if (wurzel.matches && wurzel.matches(auswahl)) wurzel.setAttribute('tabindex', '0');
    wurzel.querySelectorAll(auswahl).forEach(el => el.setAttribute('tabindex', '0'));
}

tabStoppsSetzen(document.body);
new MutationObserver(eintraege => {
    eintraege.forEach(m => m.addedNodes.forEach(tabStoppsSetzen));
}).observe(document.body, { childList: true, subtree: true });

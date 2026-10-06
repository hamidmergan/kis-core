/**
 * Barrierefreiheit (WCAG 2.1 AA)
 *
 * Ergänzt die Karte und die Quizze um das, was reine Maus-/Touch-Bedienung
 * nicht abdeckt:
 *   - Tastaturbedienung und Namen für die interaktiven SVG-Elemente (2.1.1, 4.1.2)
 *   - Zoom-Schaltflächen als Alternative zu Mausrad und Pinch (2.5.1)
 *   - Live-Regionen, damit Statusmeldungen angesagt werden (4.1.3)
 *
 * Wird nach main.js geladen und von dort angestoßen.
 */

// ============================================================
// Namen für Kartenelemente
// ============================================================

/**
 * Beschriftungen der Quick-Access-Buttons auf der Karte.
 * Die Reihenfolge hier ist zugleich die Tab-Reihenfolge der Links.
 */
const MAP_BUTTON_LABELS = {
    Button_Studium: t('map.btn.Button_Studium'),
    Button_Speiseplan: t('map.btn.Button_Speiseplan'),
    Button_Erkundungstour: t('map.btn.Button_Erkundungstour'),
    Button_Hochschulsport: t('map.btn.Button_Hochschulsport'),
    Button_FabLab: t('map.btn.Button_FabLab'),
    Button_Innenstadt: t('map.btn.Button_Innenstadt')
};

/**
 * Zwei Haltestellen-Paare tragen in config.js denselben Titel (je eine pro
 * Fahrtrichtung). Gleichlautende Namen sind für Screenreader nicht
 * unterscheidbar, deshalb hängen wir die Richtung aus der ID an.
 */
const BUS_RICHTUNG = {
    Bus_Bessemer_Straße_Sereetz: t('map.towards', { place: 'Sereetz' }),
    Bus_Bessemer_Straße_Bornkamp: t('map.towards', { place: 'Bornkamp' }),
    Bus_Technische_Hochschule_Sereetz: t('map.towards', { place: 'Sereetz' }),
    Bus_Technische_Hochschule_Grillenweg: t('map.towards', { place: 'Grillenweg' })
};

/**
 * Anzeigenamen der Elementarten. Die Schlüssel (meta.art) bleiben deutsch,
 * weil an ihnen Sortierung und Rollen hängen.
 */
const MAP_ART_LABELS = {
    'Gebäude': t('map.type.building'),
    'Café': t('map.type.cafe'),
    'Fahrradstation': t('map.type.bike'),
    'Bushaltestelle': t('map.type.bus'),
    'Quiz': t('map.type.quiz'),
    'Link': t('map.type.link')
};

/** Karten-Element-ID -> Quiz-ID (dieselbe Zuordnung wie in colorQuizElements). */
const MAP_QUIZ_IDS = {
    'Frage': 'Frage', 'Frage-2': 'Frage2', 'Frage-3': 'Frage3',
    'Frage-4': 'Frage4', 'Frage-5': 'Frage5', 'Frage-6': 'Frage6',
    'Frage-7': 'Frage7', 'Frage-8': 'Frage8', 'Frage-9': 'Frage9',
    'Frage-10': 'Frage10'
};

/**
 * Baut den Index aller bedienbaren Kartenelemente auf.
 *
 * Bewusst nur Elemente, die auch wirklich etwas auslösen: Die Übergänge
 * zwischen den Gebäuden stehen zwar in CLICKABLE_Geb_CONFIG, haben aber
 * keinen Eintrag in campusBuildings – ein Klick darauf tut nichts. Solche
 * Elemente würden als leere Tab-Stationen nur im Weg stehen.
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

/**
 * Setzt den vollständigen Namen für ein Kartenelement zusammen.
 * Screenreader lesen role="button" selbst vor, deshalb steht die Art
 * (Gebäude, Café, …) und nicht das Wort „Schaltfläche“ im Namen.
 */
function mapElementLabel(id, meta) {
    if (meta.art === 'Quiz') {
        const geloest = typeof getCompletedQuizIds === 'function'
            && getCompletedQuizIds().includes(MAP_QUIZ_IDS[id]);
        return `${meta.name}${geloest ? t('map.solved') : ''}`;
    }
    if (meta.art === 'Link') {
        return `${meta.name} ${t('map.newWindow')}`;
    }
    // „Gebäude E.5“ statt „Gebäude: Gebäude E.5“
    const art = MAP_ART_LABELS[meta.art] || meta.art;
    if (meta.name.startsWith(art)) return meta.name;
    return `${art}: ${meta.name}`;
}

// ============================================================
// Tab-Reihenfolge auf der Karte (2.4.3)
// ============================================================
//
// Im SVG stehen die Elemente in ihrer Zeichenreihenfolge –
// für Tab ergibt das Sprünge quer über die Karte. Umsortieren lässt sich das
// DOM nicht (die Reihenfolge bestimmt, was obenauf gezeichnet wird). Deshalb:
//   - nur das erste Element der Karte ist per Tab erreichbar (tabindex 0),
//     alle anderen haben tabindex -1,
//   - Tab / Umschalt+Tab innerhalb der Karte springen nach MAP_TAB_ORDER,
//   - am Anfang bzw. Ende geht der Fokus normal aus der Karte heraus.

/** Reihenfolge der Gruppen beim Durchtabben. */
const MAP_GRUPPEN_REIHENFOLGE = ['Gebäude', 'Quiz', 'Café', 'Fahrradstation', 'Bushaltestelle', 'Link'];

/**
 * Sortierschlüssel innerhalb einer Gruppe.
 * Gebäude: nach Campusbereich (A–G) und Nummer, also A.1, B.59, B.60 … G.3;
 * Gebäude ohne Bereichskennung (MFC, GründerCube) danach.
 */
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
        // Reihenfolge aus MAP_BUTTON_LABELS, das Logo zum Schluss
        const pos = Object.keys(MAP_BUTTON_LABELS).indexOf(id);
        return String(pos < 0 ? 999 : pos).padStart(3, '0');
    }
    return meta.name;
}

/** IDs aller Kartenelemente in Tab-Reihenfolge. */
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

/** Die aktuell bedienbaren Kartenelemente (eingeblendet), in Tab-Reihenfolge. */
function mapTabElements() {
    const svg = document.querySelector('#lottieMap svg');
    if (!svg) return [];
    return mapTabOrder
        .map(id => svg.querySelector(`[data-a11y-id="${CSS.escape(id)}"]`))
        .filter(el => el && el.dataset.a11ySichtbar === 'true');
}

/** Nur das erste bedienbare Element bleibt ein normaler Tab-Stopp. */
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

    // Rand der Karte erreicht: Der Browser soll normal weitertabben. Dabei
    // darf er nicht auf dem Einstiegselement (tabindex 0) landen, das im DOM
    // irgendwo zwischen den anderen liegt – also kurz herausnehmen.
    const einstieg = elemente[0];
    if (einstieg && einstieg !== aktuell) {
        einstieg.setAttribute('tabindex', '-1');
        window.setTimeout(() => einstieg.setAttribute('tabindex', '0'), 0);
    }
    if (e.shiftKey && pos === 0) {
        // Von ganz vorne zurück: vor die Karte, also auf den letzten Zoom-Button
        const zoom = document.querySelectorAll('.map-controls button');
        if (zoom.length) {
            e.preventDefault();
            zoom[zoom.length - 1].focus();
        }
    }
}

/**
 * Hält das fokussierte Element im sichtbaren Ausschnitt. Ist die Karte
 * hineingezoomt, kann der Fokus sonst außerhalb des Bildes landen (2.4.7).
 */
function keepMapFocusInView(e) {
    const el = e.target.closest && e.target.closest('[data-a11y-id]');
    if (el && window.mapZoomControls && window.mapZoomControls.panToElement) {
        window.mapZoomControls.panToElement(el);
    }
}

// ============================================================
// Tastatur- und ARIA-Schicht auf der Karte
// ============================================================

let mapLabelIndex = null;

/**
 * Macht die interaktiven SVG-Gruppen fokussierbar, benennt sie und
 * verdrahtet Enter/Leertaste auf dieselbe Aktion wie ein Klick.
 * Wird aufgerufen, sobald das Karten-SVG im DOM steht.
 */
function setupMapAccessibility() {
    const svg = document.querySelector('#lottieMap svg');
    if (!svg) return;

    mapLabelIndex = buildMapLabelIndex();

    // Die Karte als benannter Bereich – sonst ist sie im Screenreader namenlos.
    const container = document.getElementById('mapContainer');
    if (container) {
        container.setAttribute('aria-label', t('map.containerLabel'));
    }
    // Bewusst kein <title> im SVG: Browser zeigen es als Hover-Tooltip über der
    // ganzen Karte an. Der zugängliche Name kommt allein aus aria-label.
    svg.setAttribute('role', 'group');
    svg.setAttribute('aria-label', t('map.svgLabel'));
    // Chrome macht das SVG sonst als scrollbaren Bereich selbst zum Tab-Stopp –
    // ein leerer Halt zwischen Zoom-Buttons und erstem Gebäude.
    svg.setAttribute('tabindex', '-1');

    // Gruppen benennen, damit die Elemente im Screenreader sortiert wirken
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
        // Links öffnen eine Website und werden auch als Link angesagt
        el.setAttribute('role', meta.art === 'Link' ? 'link' : 'button');
        el.setAttribute('tabindex', '-1');
        el.setAttribute('aria-label', mapElementLabel(id, meta));
        el.dataset.a11yId = id;
    });

    mapTabOrder = buildMapTabOrder(mapLabelIndex);
    svg.addEventListener('keydown', handleMapTab);
    svg.addEventListener('focusin', keepMapFocusInView);

    // Enter und Leertaste lösen dieselbe Aktion aus wie ein Klick.
    svg.addEventListener('keydown', e => {
        if (e.key !== 'Enter' && e.key !== ' ' && e.key !== 'Spacebar') return;
        const ziel = e.target.closest('[data-a11y-id]');
        if (!ziel) return;
        e.preventDefault();
        e.stopPropagation();
        activateMapTarget(ziel);
    });

    // Escape auf der Karte beendet die Tastaturauswahl: Der Fokus geht auf den
    // Kartenbereich selbst (ohne Rahmen), der nächste Tab beginnt wieder vorn
    // bei den Zoom-Buttons.
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

/**
 * Hält Fokussierbarkeit und Namen aktuell.
 *
 * Ausgeblendete Kartenelemente (Einstellungen -> Kartenelemente) dürfen keine
 * Tab-Stationen bleiben: Ihre Kinder stehen auf display:none, das Element
 * selbst bliebe sonst als unsichtbarer Fokuspunkt zurück.
 */
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
// Zoom-Schaltflächen (2.5.1: Alternative zu Mausrad und Pinch)
// ============================================================

/** Baut die Zoom-Bedienelemente in den Kartencontainer. */
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
    // Im DOM vor der Karte: So sind die Zoom-Buttons per Tab direkt nach dem
    // Kopfbereich erreichbar und nicht erst nach allen Kartenelementen.
    // Die Position auf dem Bildschirm regelt das CSS.
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
// Statusmeldungen (4.1.3)
// ============================================================

/**
 * Sagt eine Statusmeldung über die Live-Region an.
 * Der Umweg über das kurze Leeren erzwingt die Ansage auch dann,
 * wenn derselbe Text zweimal hintereinander kommt.
 */
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
// Verdrahtung mit main.js
// ============================================================
//
// main.js ruft diese Funktionen an mehreren Stellen auf. Statt jede
// Aufrufstelle anzufassen, hängen wir uns einmal an die Funktionen selbst –
// das hält die Barrierefreiheits-Logik an einem Ort.

/** setupZoomPan() läuft, sobald das Karten-SVG im DOM steht. */
if (typeof window.setupZoomPan === 'function') {
    const zoomPanBasis = window.setupZoomPan;
    window.setupZoomPan = function () {
        const ergebnis = zoomPanBasis.apply(this, arguments);
        setupMapAccessibility();
        setupMapZoomControls();
        return ergebnis;
    };
}

/** Ein- und Ausblenden von Kartenelementen ändert, was fokussierbar sein darf. */
if (typeof window.updateFilterStyles === 'function') {
    const filterBasis = window.updateFilterStyles;
    window.updateFilterStyles = function () {
        const ergebnis = filterBasis.apply(this, arguments);
        syncMapA11yState();
        return ergebnis;
    };
}

/** Gelöste Quizze bekommen den Zusatz „bereits gelöst“ in den Namen. */
if (typeof window.colorQuizElements === 'function') {
    const quizFarbenBasis = window.colorQuizElements;
    window.colorQuizElements = function () {
        const ergebnis = quizFarbenBasis.apply(this, arguments);
        syncMapA11yState();
        return ergebnis;
    };
}

// ============================================================
// Quiztypen, die von Haus aus nur Maus/Touch kennen
// ============================================================

/**
 * Memory: Die Karten sind seit Phase 3 <button> und damit von selbst
 * bedienbar. Hier bleibt, den Zustand vorzulesen – verdeckt, aufgedeckt,
 * Paar gefunden – und gefundene Paare aus dem Tab-Weg zu nehmen.
 */
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

    // Die Klassen werden an mehreren Stellen und teils zeitversetzt gesetzt
    // (Flip-Animation). Ein Beobachter trifft alle Wege zuverlässig.
    if (grid._a11yObserver) grid._a11yObserver.disconnect();
    let letzterStand = -1;
    let aufgedeckt = new Set();
    grid._a11yObserver = new MutationObserver(() => {
        aktualisiere();

        // Fokus bleibt beim Umdrehen auf der Karte; die Namensänderung allein
        // lesen Screenreader nicht zuverlässig vor – deshalb ansagen.
        const offen = new Set([...grid.querySelectorAll('.memory-card.flipped:not(.matched)')]);
        const neu = [...offen].filter(k => !aufgedeckt.has(k));
        aufgedeckt = offen;
        if (neu.length) {
            let text = t('memory.turned', { names: neu.map(k => k.dataset.cardLabel || t('memory.image')).join(', ') });
            // Kein Paar: Die beiden Karten bleiben offen, bis die nächste
            // Karte aufgedeckt wird (so ist es in main.js gelöst).
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
 * Wortsuche: Ersetzt die Ziehgeste durch Anker + Cursor.
 *
 * Pfeiltasten bewegen den Cursor, Enter setzt den ersten Buchstaben,
 * ein zweites Enter bestätigt das Wort, Escape bricht ab. Anders als beim
 * Ziehen mit der Maus zählt nur eine exakt gerade Linie – das ist mit der
 * Tastatur vorhersehbarer als die Toleranzlogik der Mausvariante.
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
 * Bild-Hotspot: Legt ein unsichtbares Raster aus fokussierbaren Bereichen
 * über das Bild.
 *
 * Die Bereiche tragen bewusst neutrale Namen ("Zeile 2, Spalte 3") – stünde
 * dort der Hotspot-Text, wäre das Rätsel für Screenreader-Nutzer gelöst,
 * bevor es beginnt.
 *
 * pointer-events:none in der CSS sorgt dafür, dass Mausklicks weiterhin
 * punktgenau am Overlay ankommen und nicht auf Rasterfelder gerundet werden.
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
            // Roving tabindex: nur ein Feld ist Tab-Stopp, der Rest per Pfeiltasten
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
        // Sonst greift zusaetzlich der delegierte Overlay-Handler in main.js
        e.stopPropagation();

        const r = +feld.dataset.row, c = +feld.dataset.col;
        const x0 = c * 100 / SPALTEN, x1 = (c + 1) * 100 / SPALTEN;
        const y0 = r * 100 / ZEILEN, y1 = (r + 1) * 100 / ZEILEN;

        // Schneidet ein noch nicht gefundener Hotspot dieses Feld?
        const gefunden = container._hotspotFound || new Set();
        let treffer = null;
        hotspots.forEach((h, i) => {
            if (treffer || gefunden.has(i)) return;
            const nx = Math.max(x0, Math.min(x1, h.x));
            const ny = Math.max(y0, Math.min(y1, h.y));
            if (Math.hypot(h.x - nx, h.y - ny) <= h.radius) treffer = h;
        });

        // Die eigentliche Auswertung macht weiterhin main.js – gleicher Code
        // fuer Maus und Tastatur, inklusive Markern und Fortschritt.
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

// --- Anbindung an die Init-Funktionen aus main.js ---

if (typeof window.initMemoryGame === 'function') {
    const basis = window.initMemoryGame;
    window.initMemoryGame = function (container) {
        const ergebnis = basis.apply(this, arguments);
        // initMemoryGame baut beim Neumischen zeitversetzt auf (Fade-Animation)
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
// Fokusführung beim Öffnen und Schließen (2.4.3)
// ============================================================
//
// Bootstrap gibt den Fokus nach dem Schließen an das Element zurück, das
// das Panel per data-bs-toggle geöffnet hat. Die Kartenelemente öffnen aber
// programmatisch – Bootstrap kennt den Auslöser also nicht und der Fokus
// fällt auf <body>. Für Tastaturnutzer hieße das: zurück an den Anfang und
// erneut durch alle Kartenelemente tabben. Deshalb merken wir uns selbst,
// von wo aus geöffnet wurde.

let letzterKartenFokus = null;

// Wurde zuletzt mit Tastatur oder mit Maus/Touch bedient? Nach einem
// Mausklick soll das Kartenelement beim Schließen keinen Fokusrahmen
// bekommen – der ist nur für Tastaturnutzer sinnvoll.
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
    // Nur zurückgeben, wenn das Element noch bedienbar ist – es könnte
    // inzwischen über die Einstellungen ausgeblendet worden sein.
    if (ziel.dataset.a11ySichtbar !== 'true') return;
    ziel.focus();
}

document.addEventListener('hidden.bs.offcanvas', fokusZurueckGeben);

// Das Badges-Panel wird per JavaScript geöffnet, Bootstrap kennt den Auslöser
// nicht – ohne Hilfe landet der Fokus nach dem Schließen auf <body>.
document.addEventListener('hidden.bs.offcanvas', e => {
    if (e.target.id !== 'badgesOffcanvas') return;
    // Beim Ereignis steht der Fokus oft noch im gerade ausgeblendeten Panel
    const a = document.activeElement;
    if (!a || a === document.body || e.target.contains(a)) {
        const btn = document.getElementById('toolboxBadgesBtn');
        if (btn) btn.focus();
    }
});

// Auf dem Smartphone liegen Badges und Einstellungen im zugeklappten Menü.
// Ihr Button ist dann unsichtbar und kann den Fokus nicht nehmen, also
// bekommt ihn der Menü-Button.
document.addEventListener('hidden.bs.offcanvas', e => {
    if (e.target.id !== 'badgesOffcanvas' && e.target.id !== 'filterOffcanvas') return;
    const a = document.activeElement;
    if (a && a !== document.body && !e.target.contains(a)) return;
    const menuBtn = document.getElementById('toolboxMenuBtn');
    if (menuBtn && menuBtn.offsetParent) menuBtn.focus();
});
document.addEventListener('hidden.bs.modal', fokusZurueckGeben);

// ============================================================
// Sichtbarkeitsänderungen ansagen (4.1.3)
// ============================================================
//
// Beim Ein- und Ausblenden von Kartenelementen ändert sich die Karte, ohne
// dass sich der Fokus bewegt – ohne Ansage bleibt die Änderung für
// Screenreader-Nutzer unbemerkt.

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
    // Der Button-Zustand wird erst im Handler von main.js aktualisiert
    window.setTimeout(() => {
        const btn = document.getElementById('toggleAllBtn');
        if (!btn) return;
        announce(btn.classList.contains('active')
            ? t('announce.allShown')
            : t('announce.allHidden'));
    }, 100);
});

// ============================================================
// Info-Schaltfläche im Quiz-Modal (2.1.1, 4.1.2)
// ============================================================
//
// Der Auslöser ist ein <div>, dessen Klick-Logik an Icon und „Schließen“-Text
// hängt (und bei jedem Umschalten neu aufgebaut wird). Statt das umzubauen,
// bekommt der Container Rolle, Fokus und Namen; Enter/Leertaste klicken das
// jeweils vorhandene Icon.

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

// Nach main.js: setupAccordionToggle klont den Container beim Öffnen,
// deshalb erst danach (setTimeout) verstärken.
document.addEventListener('shown.bs.modal', e => {
    window.setTimeout(() => enhanceInfoTrigger(e.target), 0);
});

// ============================================================
// Fokus nach „Prüfen“ / „Nochmal versuchen“ (2.4.3)
// ============================================================
//
// main.js blendet den gedrückten Button aus (display:none). Der Fokus fällt
// dann auf <body>: Die Tastaturposition ist weg und Escape schließt das
// Modal nicht mehr, weil Bootstrap es nur bei Fokus im Dialog hört. Deshalb
// bekommt der jeweils andere, jetzt sichtbare Button den Fokus.

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
// Sortier-Quiz: Verschieben ansagen (4.1.3)
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
// Quiz-Dialoge: Frage als Beschreibung, Antworten als Gruppe (1.3.1)
// ============================================================
//
// Beim Öffnen sagt der Screenreader sonst nur „Quiz 3, Dialog“ – die Frage
// selbst müsste man erst suchen. Und die Antwortmöglichkeiten wären lose
// Kontrollkästchen ohne Bezug zur Frage.

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
// Bilderkarussell in der Gebäude-Info (2.2.2 Pausieren, Beenden)
// ============================================================
//
// Die Bilder wechseln alle 3 Sekunden von selbst. Dafür braucht es eine
// Möglichkeit zum Anhalten. Außerdem stoppt der Wechsel, solange der
// Tastaturfokus im Karussell ist (sonst wechselt das Bild unter der Hand),
// und ein von Hand gewähltes Bild wird angesagt.

function enhanceBuildingCarousel() {
    const el = document.getElementById('carouselBuilding');
    if (!el || el.querySelector('.carousel-pause-btn') || typeof bootstrap === 'undefined') return;
    const inst = bootstrap.Carousel.getOrCreateInstance(el);

    let angehalten = false;   // vom Nutzer per Button
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
    // nach main.js, das im selben Ereignis das Karussell startet
    window.setTimeout(enhanceBuildingCarousel, 0);
});

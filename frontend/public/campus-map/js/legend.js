// ============================================================
// Gebäude & Legende
// ============================================================
//
// Inhalt der Legende aus dem offiziellen Campusplan (PDF, rechte Seite):
// Einrichtungen A–Z und Gebäudenummern neu/alt. Die Suche findet außerdem
// Gebäude, Cafés, Bushaltestellen und Fahrradstationen.
//
// Die Legende lebt im rechten Panel (#buildingInfoOffcanvas), das auch die
// Gebäude-Details zeigt. Auf dem Smartphone ist das Panel ein Bottom-Sheet.
// Ablauf: Legende → Eintrag antippen → Gebäude-Details → „‹ Legende“ zurück.
// „Auf Karte zeigen“ fliegt zum Gebäude und hebt es hervor; auf kleinen
// Bildschirmen schließt sich dabei das Sheet und eine Leiste am unteren Rand
// führt zurück zu den Infos.
//
// Texte: UI-Texte über t() (i18n.js), Inhalte hier direkt zweisprachig.

// --- Bereiche (Farben aus den Gebäude-Icons: kräftig + hell) ---
const LEGEND_AREAS = [
    { key: 'A', color: '#e4003a', tint: '#fcdad4' },
    { key: 'B', color: '#008a8b', tint: '#d1e5e8' },
    { key: 'C', color: '#0092c3', tint: '#dde9f5' },
    { key: 'D', color: '#8c9b39', tint: '#ecf0dc' },
    { key: 'E', color: '#0e5f8f', tint: '#d6dae7' },
    { key: 'F', color: '#44904a', tint: '#dde7da' },
    { key: 'G', color: '#8e195a', tint: '#e5cfdb' },
    { key: 'MFC', color: '#6a7078', tint: '#e7e7ea' }
];

// --- Gebäude: neue Nummer, alte Nummer (PDF „Gebäudenummern neu/alt“) ---
// name: nur wo das Gebäude einen eigenen Namen hat
const LEGEND_BUILDINGS = [
    { code: 'A.1', id: 'Gebaeude_A_1', area: 'A', old: '36' },
    { code: 'B.59', id: 'Mensa_B_59', area: 'B', name: { de: 'Mensa', en: 'Mensa (dining hall)' } },
    { code: 'B.60', id: 'Bibliothek_B_60', area: 'B', name: { de: 'Bibliothek', en: 'Library' } },
    { code: 'B.64', id: 'Gebaeude_B_64', area: 'B' },
    { code: 'B.65', id: 'Audimax_B_65', area: 'B', name: { de: 'Audimax', en: 'Audimax' } },
    { code: 'C.1', id: 'Gebaeude_C_1', area: 'C', old: '11' },
    { code: 'C.2a', id: 'Gebaeude_C_2a', area: 'C', old: '10' },
    { code: 'C.2b', id: 'Gebaeude_C_2b', area: 'C', old: '9' },
    { code: 'C.3', id: 'Gebaeude_C_3', area: 'C', old: '2' },
    { code: 'C.4', id: 'Gebaeude_C_4', area: 'C', old: '1' },
    { code: 'D.1', id: 'Gebaeude_D_1', area: 'D', old: '24' },
    { code: 'D.2', id: 'Gebaeude_D_2', area: 'D', old: '20' },
    { code: 'D.3', id: 'Gebaeude_D_3', area: 'D', old: '20a' },
    { code: 'D.4', id: 'Gebaeude_D_4', area: 'D', old: '25' },
    { code: 'E.1', id: 'Gebaeude_E_1', area: 'E', old: '14' },
    { code: 'E.2', id: 'Gebaeude_E_2', area: 'E', name: { de: 'Bauforum', en: 'Bauforum' } },
    { code: 'E.3', id: 'Gebaeude_E_3', area: 'E', old: '15' },
    { code: 'E.4', id: 'Gebaeude_E_4', area: 'E', old: '15b' },
    { code: 'E.5', id: 'Gebaeude_E_5', area: 'E', old: '16' },
    { code: 'F.1', id: 'Gebaeude_F_1', area: 'F', old: '8' },
    { code: 'F.2', id: 'Gebaeude_F_2', area: 'F', old: '7' },
    { code: 'F.3', id: 'Gebaeude_F_3', area: 'F', old: '6' },
    { code: 'F.4', id: 'Gebaeude_F_4', area: 'F', old: '5' },
    { code: 'F.5', id: 'Gebaeude_F_5', area: 'F', old: '4' },
    { code: 'F.6', id: 'Gebaeude_F_6', area: 'F', old: '3' },
    { code: 'F.7', id: 'Gebaeude_F_7', area: 'F', old: '3a' },
    { code: 'F.8', id: 'Gebaeude_F_8', area: 'F', old: '19/19a' },
    { code: 'F.9', id: 'Gebaeude_F_9', area: 'F', old: '21' },
    { code: 'G.1', id: 'Gebaeude_G_1', area: 'G', old: '13' },
    { code: 'G.2', id: 'Gebaeude_G_2', area: 'G', old: '17' },
    { code: 'G.3', id: 'Gebaeude_G_3', area: 'G', old: '18' },
    { code: 'MFC 1', id: 'MFC_1', area: 'MFC' },
    { code: 'MFC 7', id: 'MFC_7', area: 'MFC' },
    { code: 'MFC 8', id: 'MFC_8', area: 'MFC' },
    { code: 'GC 1', id: 'GruenderCube_1', area: 'MFC', name: { de: 'GründerCube 1', en: 'GründerCube 1' } },
    { code: 'GC 2', id: 'GruenderCube_2', area: 'MFC', name: { de: 'GründerCube 2', en: 'GründerCube 2' } }
];

// --- Einrichtungen A–Z (PDF), in: Gebäudenummern ---
// open: optional eigene Detailseite statt des Gebäudes
const LEGEND_FACILITIES = [
    { de: 'Angewandte Naturwissenschaften (AN), Sekretariat', en: 'Applied Natural Sciences, Secretariat', in: ['G.1'] },
    { de: 'AStA-Cafeteria / AStA-Shop', en: 'AStA Cafeteria, AStA Shop', in: ['D.4'] },
    { de: 'AStA', en: 'AStA', in: ['E.4'] },
    { de: 'Audimax', en: 'Audimax', in: ['B.65'] },
    { de: 'Bauforum (Bau)', en: 'Bauforum', in: ['E.2'] },
    { de: 'Bauwesen, Sekretariat', en: 'Architecture & Civil Engineering, Secretariat', in: ['E.1'] },
    { de: 'Bibliothek', en: 'Library', in: ['B.60'] },
    { de: 'Cafeteria', en: 'Cafeteria', in: ['C.4'] },
    { de: 'Druckerei', en: 'Print Shop', in: ['A.1'] },
    { de: 'Elektrotechnik und Informatik (EI), Sekretariat', en: 'Electrical Engineering & Computer Science, Secretariat', in: ['C.3'] },
    { de: 'Fachschaften', en: 'Student Councils', in: ['E.4'] },
    // mark: statt Gebäuden alle Stationen auf der Karte markieren (kein Hinspringen)
    { de: 'Fahrradreparaturpunkte', en: 'Bike Repair Points', in: [], icon: 'assets/fahrrad_icon_einstellungen_an.svg',
        keywords: 'Fahrrad Fahrradstation Rad Bike Reparatur Repair',
        mark: ['Fahrradstation_Gebaeude_C_4', 'Fahrradstation_Gebaeude_G_1', 'Fahrradstation_Wohnheim', 'Fahrradstation_Studentendorf', 'Fahrradstation_Audimax'] },
    { de: 'Haustechnik', en: 'Facility Management', in: ['C.4'] },
    { de: 'International Office', en: 'International Office', in: ['A.1'] },
    { de: 'IT-Support', en: 'IT Support', in: ['D.4'] },
    { de: 'JuniorCampus', en: 'JuniorCampus', in: ['D.1'] },
    { de: 'Marktüberwachung SH', en: 'Market Surveillance SH', in: ['F.7'] },
    { de: 'Maschinenbau und Wirtschaft (MW), Sekretariat', en: 'Mechanical Engineering & Business Administration, Secretariat', in: ['C.3'] },
    { de: 'Materialprüfanstalt SH', en: 'Material Testing Institute SH', in: ['F.6'] },
    { de: 'Mensa', en: 'Mensa (dining hall)', in: ['B.59'] },
    { de: 'Präsidium', en: 'University Board', in: ['A.1'] },
    { de: 'Pressestelle', en: 'Press Office', in: ['D.4'] },
    { de: 'Service-Point', en: 'Service Point', in: ['A.1'], servicePoint: true },
    { de: 'Sprachenzentrum', en: 'Language Center', in: ['A.1'] },
    { de: 'Stabsstelle Forschung und Transfer', en: 'Research and Transfer', in: ['A.1'] },
    { de: 'Still- und Wickelraum', en: 'Nursing Room', in: ['G.2', 'D.4'] },
    { de: 'Studienberatung', en: 'Student Advisory Service', in: ['A.1'] },
    { de: 'StuPa', en: 'StuPa Student Parliament', in: ['E.4'] },
    { de: 'Verwaltung', en: 'Administration', in: ['A.1', 'E.5'] },
    { de: 'Zulassungsstelle', en: 'Admissions Office', in: ['A.1'] }
];

// Schnellzugriff oben in „Einrichtungen“ (deutscher Name aus der Liste)
const LEGEND_POPULAR = ['Mensa', 'Audimax', 'Bibliothek', 'International Office', 'Service-Point', 'Studienberatung', 'Druckerei'];

// Weitere Orte aus campusBuildings (eigene Detailseiten, keine Gebäude)
const LEGEND_PLACE_GROUPS = [
    { key: 'food', prefix: 'Kaffee_', color: '#c2571a', tint: '#fdebd3', name: { de: 'Essen & Trinken', en: 'Food & drink' }, keywords: 'Café Kaffee Coffee Snacks Essen Food' },
    { key: 'mobility', prefix: ['Bus_', 'Fahrradstation_'], color: '#4b5459', tint: '#eceef0', name: { de: 'Bus & Fahrrad', en: 'Bus & bike' }, keywords: 'Haltestelle Bus stop Fahrrad Rad Bike' }
];

// --- Suchbegriffe je Gebäude/Ort (aus den Beschreibungen in config_v2.js) ---
// Findet z.B. „Atrium“ → C.4. In den Treffern steht der passende Begriff
// unter dem Gebäude. Beim Ändern der Beschreibungen hier nachziehen.
const BIKE_TERMS = { de: ['Fahrradreparatur', 'Reparatur', 'Werkzeug', 'Luftpumpe', 'Pumpe'], en: ['bike repair', 'repair', 'tools', 'air pump', 'pump'] };
const LEGEND_SEARCH_TERMS = {
    Mensa_B_59: { de: ['Essen', 'Mittagessen', 'Kantine', 'Wickeltisch', 'Spielecke'], en: ['food', 'lunch', 'canteen', 'dining hall', 'changing table'] },
    Audimax_B_65: { de: ['Hörsaal', 'Hörsaalzentrum', 'AM 1', 'AM 2', 'AM 3', 'Vorlesung', 'Veranstaltungen'], en: ['lecture hall', 'lectures', 'events'] },
    Bibliothek_B_60: { de: ['Hochschulbibliothek', 'ZHB', 'Bücher', 'Lernen', 'PC-Pool', 'Ruhearbeitsraum', 'Gruppenarbeitsraum', 'Studi-Lounge'], en: ['books', 'study', 'quiet study room', 'group study room', 'computer pool'] },
    Gebaeude_B_64: { de: ['Biomedizintechnik', 'TANDEM', 'Universität zu Lübeck', 'Technische Informatik', 'Neuroinformatik', 'Bioinformatik', 'Informationssysteme', 'IT-Sicherheit', 'IT-Service-Center', 'IMIS'], en: ['biomedical engineering', 'University of Lübeck', 'computer engineering', 'IT security'] },
    MFC_7: { de: ['ISy', 'Institut für Interaktive Systeme', 'ZDL', 'Zentrum für Digitale Lehre', 'Learning Analytics', 'KI'], en: ['interactive systems', 'digital teaching', 'AI'] },
    MFC_8: { de: ['FabLab', '3D-Druck', 'Lasercutter', 'CNC', 'Werkstatt', 'IPSY', 'Psychologie'], en: ['3D printing', 'laser cutter', 'makerspace', 'psychology'] },
    MFC_1: { de: ['TZL', 'Technikzentrum', 'Campus Taste', 'Bürogebäude'], en: ['technology centre', 'office building'] },
    Gebaeude_G_1: { de: ['Labor', 'Biotechnologie', 'CIB', 'Angewandte Naturwissenschaften'], en: ['lab', 'biotechnology', 'applied natural sciences'] },
    Gebaeude_G_2: { de: ['Labor', 'Angewandte Naturwissenschaften', 'Maschinenbau', 'Wickelraum', 'Stillraum'], en: ['lab', 'mechanical engineering', 'nursing room', 'baby changing'] },
    Gebaeude_G_3: { de: ['Labor', 'CoSA', 'Elektrotechnik', 'Informatik'], en: ['lab', 'electrical engineering', 'computer science'] },
    GruenderCube_1: { de: ['Gründung', 'Gründungsberatung', 'Start-up', 'Startup', 'Workshops'], en: ['startup', 'founders', 'entrepreneurship'] },
    GruenderCube_2: { de: ['Gründung', 'Gründungsberatung', 'Start-up', 'Startup', 'Arbeitsräume'], en: ['startup', 'founders', 'workspace'] },
    Gebaeude_E_5: { de: ['Hochschulverwaltung', 'Betriebsarzt'], en: ['administration', 'company doctor'] },
    Gebaeude_E_4: { de: ['Fachschaft', 'Studierendenparlament', 'Allgemeiner Studierendenausschuss'], en: ['student council', 'student union', 'student parliament'] },
    Gebaeude_E_3: { de: ['Labor', 'Bauwesen'], en: ['lab', 'civil engineering'] },
    Gebaeude_E_2: { de: ['Foyer', 'Ausstellung', 'Veranstaltungsort', 'Bauwesen'], en: ['exhibition', 'events', 'civil engineering'] },
    Gebaeude_E_1: { de: ['Vorlesungsräume', 'Bauwesen', 'Baustofflabor', 'Hydrologie', 'Wasserwirtschaft', 'RoboLab'], en: ['lecture rooms', 'civil engineering', 'building materials lab', 'hydrology', 'robotics'] },
    Gebaeude_A_1: { de: ['Hochschulverwaltung', 'Personal', 'Finanzen', 'Studierendensekretariat', 'Immatrikulation', 'Bewerbung', 'Besuchersekretariat'], en: ['administration', 'human resources', 'finance', "registrar's office", 'enrolment', 'application'] },
    Gebaeude_D_4: { de: ['Hörsaal', 'Vorlesungssäle', 'Orientierungssemester', 'LOS', 'Arbeitsplätze', 'Wickelraum'], en: ['lecture hall', 'orientation semester', 'study spaces', 'IT help'] },
    Gebaeude_D_3: { de: ['Seagulls', 'Formula Student', 'Rennwagen', 'Rennteam'], en: ['racing team', 'race car'] },
    Gebaeude_D_2: { de: ['Solarhaus', 'Solar', 'Photovoltaik', 'Sonnensimulator', 'Thermoelektrik', 'Reallabor'], en: ['solar house', 'photovoltaics', 'solar simulator'] },
    Gebaeude_D_1: { de: ['Kinder', 'Experimente', 'MINT'], en: ['children', 'kids', 'experiments', 'STEM'] },
    Gebaeude_C_4: { de: ['Atrium', 'Foyer', 'Seminarräume', 'Vorlesungsräume', 'Bits+Bytes', 'Haustechnik', 'Hauptgebäude'], en: ['atrium', 'foyer', 'seminar rooms', 'lecture rooms', 'facility management', 'main building'] },
    Gebaeude_C_3: { de: ['Hörsaal', 'Elektrotechnik', 'Informatik', 'Maschinenbau'], en: ['lecture hall', 'electrical engineering', 'computer science', 'mechanical engineering'] },
    Gebaeude_C_2b: { de: ['Vorlesungsräume'], en: ['lecture rooms'] },
    Gebaeude_C_2a: { de: ['Vorlesungsräume'], en: ['lecture rooms'] },
    Gebaeude_C_1: { de: ['Labor', 'Physikalische Technik'], en: ['lab', 'physical engineering'] },
    Gebaeude_F_9: { de: ['Labor'], en: ['lab'] },
    Gebaeude_F_8: { de: ['Hochspannungslabor', 'EMV', 'Verteilerstation'], en: ['high-voltage lab', 'EMC'] },
    Gebaeude_F_7: { de: ['Marktüberwachung'], en: ['market surveillance'] },
    Gebaeude_F_6: { de: ['Materialprüfanstalt', 'MPA'], en: ['material testing'] },
    Gebaeude_F_5: { de: ['E-Technik', 'Werkstatt', 'Werkstoffprüfung', 'Maschinenbau', 'Escape-Room'], en: ['workshop', 'materials testing', 'mechanical engineering', 'escape room'] },
    Gebaeude_F_4: { de: ['Maschinenhalle', 'Werkstatt'], en: ['machine hall', 'workshop'] },
    Gebaeude_F_3: { de: ['Kesselhaus', 'Strömungslehre'], en: ['boiler house', 'fluid mechanics'] },
    Gebaeude_F_2: { de: ['Hausmeister'], en: ['caretaker'] },
    Gebaeude_F_1: { de: ['Lager'], en: ['storage'] },
    Kaffee_Campus_Taste: { de: ['Säfte', 'Burger', 'Nudeln', 'Kaffee', 'MFC 1'], en: ['juice', 'burger', 'pasta', 'coffee'] },
    Kaffee_Cafeteria: { de: ['Baguette', 'Brötchen', 'Currywurst', 'Getränke', 'Barzahlung'], en: ['sandwiches', 'drinks', 'cash'] },
    Kaffee_Kiosk: { de: ['Snacks', 'Getränke', 'Zeitschriften', 'Zeitung'], en: ['snacks', 'drinks', 'newspapers'] },
    Kaffee_Bits_Bytes: { de: ['Café-Lounge', 'Waffeln', 'Kaffee', 'Lernort', 'Desserts'], en: ['café lounge', 'waffles', 'coffee', 'study space'] },
    Fahrradstation_Gebaeude_C_4: BIKE_TERMS,
    Fahrradstation_Gebaeude_G_1: BIKE_TERMS,
    Fahrradstation_Wohnheim: { de: [...BIKE_TERMS.de, 'Wohnheim'], en: [...BIKE_TERMS.en, 'dorm'] },
    Fahrradstation_Studentendorf: { de: [...BIKE_TERMS.de, 'Studentendorf'], en: [...BIKE_TERMS.en, 'student village'] },
    Fahrradstation_Audimax: BIKE_TERMS
};

const LEGEND_ABBREVIATIONS = [
    { abbr: 'AStA', de: 'Allgemeiner Studierendenausschuss', en: 'General Students’ Committee' },
    { abbr: 'StuPa', de: 'Studierendenparlament', en: 'Student Parliament' }
];

// ============================================================

const campusLegend = (() => {
    const L = s => (s && typeof s === 'object') ? (s[CURRENT_LANG] || s.de) : s;
    const esc = s => String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
    const areaOf = key => LEGEND_AREAS.find(a => a.key === key);
    const buildingByCode = code => LEGEND_BUILDINGS.find(b => b.code === code);
    const buildingById = id => LEGEND_BUILDINGS.find(b => b.id === id);
    const contentOf = id => campusBuildings.find(b => b.id === id);
    const canHover = () => window.matchMedia('(hover: hover) and (pointer: fine)').matches;
    const isSheet = () => window.matchMedia('(max-width: 767px)').matches;

    // Für die Suche: Kleinschreibung, ohne Akzente, ß → ss
    const norm = s => String(s).toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/ß/g, 'ss');
    const compact = s => norm(s).replace(/[^a-z0-9]/g, '');

    const state = { mode: 'closed', query: '', scrollTop: 0, detailId: null, fromLegend: false };
    let panel, body, legendView, detailView, titleEl, backBtn, searchInput, clearBtn, resultsEl, pill;
    let announceTimer = null;
    let pendingAction = null;   // läuft, sobald das Panel zu ist (Smartphone)
    let pillOpen = null;        // was die Leiste unten beim Antippen öffnet
    let focusSearchOnShow = false;

    // --- Daten aufbereiten -------------------------------------------------

    function facilitiesIn(code) {
        return LEGEND_FACILITIES.filter(f => f.in.includes(code));
    }

    function facilityEntries() {
        return LEGEND_FACILITIES.map(f => {
            const buildings = f.in.map(buildingByCode).filter(Boolean);
            const hay = [f.de, f.en, ...(f.keywords || '').split(' '), ...buildings.flatMap(b => [b.code, b.old])];
            return { kind: 'facility', name: L(f), facility: f, buildings, hay };
        }).sort((a, b) => a.name.localeCompare(b.name, CURRENT_LANG));
    }

    // Suchbegriffe, Sprache der Seite zuerst (die erscheint dann im Treffer)
    function termsOf(id) {
        const t = LEGEND_SEARCH_TERMS[id];
        if (!t) return [];
        const other = CURRENT_LANG === 'de' ? 'en' : 'de';
        return [...(t[CURRENT_LANG] || []), ...(t[other] || [])];
    }

    function buildingEntries() {
        return LEGEND_BUILDINGS.filter(b => contentOf(b.id)).map(b => {
            const inside = facilitiesIn(b.code).map(L);
            const sub = b.name ? L(b.name) : inside.join(', ');
            const terms = termsOf(b.id);
            const hay = [b.code, b.old, contentOf(b.id).title, b.name?.de, b.name?.en,
                ...facilitiesIn(b.code).flatMap(f => [f.de, f.en]), ...terms];
            return { kind: 'building', building: b, id: b.id, title: contentOf(b.id).title, sub, hay, terms };
        });
    }

    function placeEntries() {
        return LEGEND_PLACE_GROUPS.flatMap(g => {
            const prefixes = [].concat(g.prefix);
            return campusBuildings
                .filter(b => prefixes.some(p => b.id.startsWith(p)))
                .map(b => {
                    const dir = (typeof BUS_RICHTUNG !== 'undefined' && BUS_RICHTUNG[b.id]) || '';
                    const terms = termsOf(b.id);
                    return { kind: 'place', group: g, id: b.id, title: b.title, sub: dir, icon: b.icon, terms,
                        hay: [b.title, dir, g.name.de, g.name.en, ...g.keywords.split(' '), ...terms] };
                });
        });
    }

    function score(entry, q) {
        const name = norm(entry.name || entry.title);
        if (name.startsWith(q)) return 0;
        if (name.split(/[\s/(),.-]+/).some(w => w.startsWith(q))) return 1;
        return 2;
    }

    // Felder einzeln prüfen: zusammengeklebt würde aus „F.3“ und „6“ ein „f36“
    function matches(entry, q, qc) {
        return entry.hay.filter(Boolean).some(field => norm(field).includes(q) || (qc && compact(field).includes(qc)));
    }

    // --- Ersatzsuche: Fragen und Tippfehler --------------------------------
    // Greift nur, wenn die normale Suche nichts findet. Aus „Wo kann ich
    // Mittag essen?“ werden die Wörter „mittag“ + „essen“, „Mesna“ findet
    // die Mensa. Angezeigt werden die Einträge, die die meisten Wörter treffen.

    // schon normalisiert (norm): ohne Umlaute, ß → ss
    const STOPWORDS = new Set((
        'wo wie was wer wann welche welcher welches ist sind gibt gibts es der die das den dem des ein eine einen einem einer ' +
        'ich man du wir kann konnen finde finden such suche brauche mochte will komme kommen hin ' +
        'mein meine meinen meinem mich mir dich dir sich uns ' +
        'zu zur zum nach in im am an auf bei mit fur und oder hier da mal bitte nachste naheste campus thl hochschule ' +
        'where how what which who is are there the a an can could i we you find get go to in at on for of and or my me ' +
        'any some please nearest closest want need look looking'
    ).split(' '));

    function queryWords(query) {
        return [...new Set(norm(query).split(/[^a-z0-9]+/).filter(w => w && !STOPWORDS.has(w)))];
    }

    // Damerau-Levenshtein (Vertauschen zweier Buchstaben zählt als 1 Fehler)
    function editDistance(a, b) {
        let prev2 = null;
        let prev = Array.from({ length: b.length + 1 }, (_, j) => j);
        for (let i = 1; i <= a.length; i++) {
            const cur = [i];
            for (let j = 1; j <= b.length; j++) {
                cur[j] = Math.min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1));
                if (prev2 && j > 1 && a[i - 1] === b[j - 2] && a[i - 2] === b[j - 1]) cur[j] = Math.min(cur[j], prev2[j - 2] + 1);
            }
            prev2 = prev;
            prev = cur;
        }
        return prev[b.length];
    }

    // grobe Stammform: „immatrikulieren“ → „immatrikul“ (findet „Immatrikulation“)
    function stem(w) {
        const suffix = ['ieren', 'ungen', 'ung', 'en', 'er', 'e', 'n', 's'].find(s => w.endsWith(s) && w.length - s.length >= 5);
        return suffix ? w.slice(0, -suffix.length) : w;
    }

    // 2 = Wort steckt im Feld, 1 = nur mit Tippfehler, 0 = kein Treffer
    function wordMatches(w, field) {
        if (compact(field) === w) return 2;                 // „c4“ → C.4
        if (w.length >= 3 && (norm(field).includes(w) || compact(field).includes(w))) return 2;
        const parts = norm(field).split(/[^a-z0-9]+/).filter(Boolean);
        if (w.length < 4) return parts.some(p => p.startsWith(w)) ? 2 : 0;
        const s = stem(w);
        if (s !== w && parts.some(p => p.startsWith(s))) return 2;
        const max = w.length >= 8 ? 2 : 1;
        return parts.some(p => Math.abs(p.length - w.length) <= max && editDistance(w, p) <= max
            // angefangenes Wort mit Tippfehler: „bibilo“ → Bibliothek
            || (w.length >= 6 && p.length > w.length && editDistance(w, p.slice(0, w.length)) <= max)) ? 1 : 0;
    }

    // Wie gut trifft der Eintrag die Wörter der Anfrage? (Summe der besten Treffer je Wort)
    function fuzzyCount(entry, words) {
        const fields = entry.hay.filter(Boolean);
        return words.reduce((sum, w) => sum + Math.max(0, ...fields.map(f => wordMatches(w, f))), 0);
    }

    // Treffer im Namen markieren (nur wenn die Schreibweise direkt passt)
    function mark(text, query) {
        if (!query) return esc(text);
        const i = text.toLowerCase().indexOf(query.toLowerCase());
        if (i < 0) return esc(text);
        return esc(text.slice(0, i)) + '<mark>' + esc(text.slice(i, i + query.length)) + '</mark>' + esc(text.slice(i + query.length));
    }

    // --- Bausteine ---------------------------------------------------------

    function swatch(buildings) {
        const colors = [...new Set(buildings.map(b => areaOf(b.area).color))];
        const bg = colors.length > 1
            ? `linear-gradient(135deg, ${colors.map((c, i) => `${c} ${i * 100 / colors.length}% ${(i + 1) * 100 / colors.length}%`).join(', ')})`
            : colors[0];
        return `<span class="legend-swatch" style="background:${bg}" aria-hidden="true"></span>`;
    }

    function codeChip(b, asButton) {
        const a = areaOf(b.area);
        const style = `--area:${a.color};--area-tint:${a.tint}`;
        if (!asButton) return `<span class="legend-code" style="${style}">${esc(b.code)}</span>`;
        return `<button type="button" class="legend-code legend-code-btn" style="${style}" data-open="${b.id}" data-highlight="${b.id}"
            aria-label="${esc(contentOf(b.id)?.title || b.code)}">${esc(b.code)}</button>`;
    }

    // Pin rechts neben der Zeile: direkt zur Karte, ohne erst die Infos zu öffnen
    function withPin(row, id, name) {
        if (!mapElement(id)) return `<li class="legend-item">${row}</li>`;
        return `<li class="legend-item has-pin">${row}
          <button type="button" class="legend-pin" data-pin="${id}" data-highlight="${id}"
            aria-label="${esc(t('legend.pinLabel', { name }))}" title="${esc(t('legend.showOnMap'))}">
            <i class="fas fa-map-marker-alt" aria-hidden="true"></i></button></li>`;
    }

    function facilityRow(e, query) {
        const f = e.facility;
        const ids = e.buildings.map(b => b.id).join(' ');
        const olds = [...new Set(e.buildings.map(b => b.old).filter(Boolean))];
        const meta = olds.length ? `<span class="legend-row-meta">${esc(t('legend.formerly', { old: olds.join(', ') }))}</span>` : '';
        const spIcon = f.servicePoint ? ' <span class="legend-sp" aria-hidden="true">i</span>' : '';
        if (f.mark) {
            const ids = f.mark.join(' ');
            return `<li class="legend-item">
              <button type="button" class="legend-row" data-mark="${ids}" data-highlight="${ids}">
                <img src="${f.icon}" alt="" class="legend-row-icon">
                <span class="legend-row-text"><span class="legend-row-name">${mark(e.name, query)}</span>
                  <span class="legend-row-meta">${esc(t('legend.markAll', { n: f.mark.length }))}</span></span>
              </button></li>`;
        }
        if (e.buildings.length === 1) {
            return withPin(`<button type="button" class="legend-row" data-open="${e.buildings[0].id}" data-highlight="${ids}">
                ${swatch(e.buildings)}
                <span class="legend-row-text"><span class="legend-row-name">${mark(e.name, query)}${spIcon}</span>${meta}</span>
                <span class="legend-codes">${codeChip(e.buildings[0], false)}</span>
              </button>`, e.buildings[0].id, e.name);
        }
        return `<li class="legend-item">
          <div class="legend-row legend-row-multi" data-highlight="${ids}">
            ${swatch(e.buildings)}
            <span class="legend-row-text"><span class="legend-row-name">${mark(e.name, query)}</span>
              <span class="legend-row-meta">${esc(t('legend.inBuildings', { n: e.buildings.length }))}</span></span>
            <span class="legend-codes">${e.buildings.map(b => codeChip(b, true)).join('')}</span>
          </div></li>`;
    }

    function resultRow(e, query) {
        if (e.kind === 'facility') return facilityRow(e, query);
        const color = e.kind === 'building' ? areaOf(e.building.area) : { color: e.group.color, tint: e.group.tint };
        const icon = e.kind === 'building' ? contentOf(e.id)?.icon : e.icon;
        const chip = e.kind === 'building' ? `<span class="legend-codes">${codeChip(e.building, false)}</span>` : '';
        return withPin(`<button type="button" class="legend-row" data-open="${e.id}" data-highlight="${e.id}" style="--area:${color.color};--area-tint:${color.tint}">
            <span class="legend-thumb">${icon ? `<img src="${icon}" alt="" loading="lazy">` : ''}</span>
            <span class="legend-row-text"><span class="legend-row-name">${mark(e.title, query)}</span>
              ${e.sub ? `<span class="legend-row-meta">${mark(e.sub, query)}</span>` : ''}</span>
            ${chip}
          </button>`, e.id, e.title);
    }

    // --- Ansichten ---------------------------------------------------------

    function renderFacilities() {
        const all = facilityEntries();
        const popular = LEGEND_POPULAR
            .map(de => LEGEND_FACILITIES.find(f => f.de === de))
            .filter(Boolean)
            .map(f => {
                const b = buildingByCode(f.in[0]);
                const a = areaOf(b.area);
                return `<button type="button" class="legend-quick-chip" style="--area:${a.color};--area-tint:${a.tint}"
                    data-open="${b.id}" data-highlight="${b.id}"><span class="legend-quick-dot" aria-hidden="true"></span>${esc(L(f).replace(/\s*\(.*\)$/, ''))}</button>`;
            }).join('');
        const abbr = LEGEND_ABBREVIATIONS.map(x => `<div><dt>${esc(x.abbr)}</dt><dd>${esc(L(x))}</dd></div>`).join('');
        return `
          <h3 class="legend-subhead">${esc(t('legend.popular'))}</h3>
          <div class="legend-quick">${popular}</div>
          <h3 class="legend-subhead">${esc(t('legend.allFacilities'))}</h3>
          <ul class="legend-list">${all.map(e => facilityRow(e, '')).join('')}</ul>
          <dl class="legend-abbr">${abbr}</dl>`;
    }

    function filterKey(f) {
        return Array.isArray(f.id) ? f.id.join(',') : f.id;
    }

    function renderSearch(query) {
        const q = norm(query.trim());
        const qc = compact(query);
        const byName = (a, b) => (a.name || a.title).localeCompare(b.name || b.title, CURRENT_LANG);
        const sort = list => list
            .filter(e => matches(e, q, qc))
            .sort((a, b) => score(a, q) - score(b, q) || byName(a, b));
        let fac = sort(facilityEntries());
        let bld = sort([...buildingEntries(), ...placeEntries()]).map(e => {
            // Nur über einen Suchbegriff gefunden? Dann den Begriff zeigen,
            // damit klar ist, warum das Gebäude in der Liste steht
            const hit = (e.terms || []).filter(term => norm(term).includes(q) || (qc && compact(term).includes(qc)));
            const byName = norm(e.title).includes(q) || norm(e.sub).includes(q);
            // erster Treffer genügt – Begriffe in Seitensprache stehen vorn
            return hit.length && !byName ? { ...e, sub: hit[0] } : e;
        });

        // Nichts gefunden? Dann als Frage bzw. mit Tippfehlern versuchen
        let fuzzy = false;
        const words = fac.length + bld.length ? [] : queryWords(query);
        if (words.length) {
            const counted = list => list.map(e => ({ e, n: fuzzyCount(e, words) })).filter(x => x.n);
            const facHits = counted(facilityEntries());
            const bldHits = counted([...buildingEntries(), ...placeEntries()]);
            const best = Math.max(0, ...facHits.map(x => x.n), ...bldHits.map(x => x.n));
            const top = hits => hits.filter(x => x.n === best).map(x => x.e).sort(byName);
            fac = top(facHits);
            bld = top(bldHits).map(e => {
                const hit = (e.terms || []).find(term => words.some(w => wordMatches(w, term)));
                const named = words.some(w => wordMatches(w, e.title) || (e.sub && wordMatches(w, e.sub)));
                return hit && !named ? { ...e, sub: hit } : e;
            });
            fuzzy = fac.length + bld.length > 0;
        }

        const n = fac.length + bld.length;
        scheduleAnnounce(n ? t('legend.resultsCount', { n }) : t('legend.noResults', { q: query.trim() }));
        if (!n) {
            return `<div class="legend-empty">
                <i class="fas fa-search-location" aria-hidden="true"></i>
                <p class="legend-empty-title">${esc(t('legend.noResults', { q: query.trim() }))}</p>
                <p>${esc(t('legend.noResultsHint'))}</p></div>`;
        }
        // ungefähre Treffer: keine Markierung, dafür ein Hinweis
        const raw = fuzzy ? '' : query.trim();
        return (fuzzy ? `<p class="legend-fuzzy-hint">${esc(t('legend.fuzzyHint', { q: query.trim() }))}</p>` : '')
            + (fac.length ? `<h3 class="legend-subhead">${esc(t('legend.facilities'))} <span class="legend-count">${fac.length}</span></h3>
              <ul class="legend-list">${fac.map(e => resultRow(e, raw)).join('')}</ul>` : '')
            + (bld.length ? `<h3 class="legend-subhead">${esc(t('legend.resultsPlaces'))} <span class="legend-count">${bld.length}</span></h3>
              <ul class="legend-list">${bld.map(e => resultRow(e, raw)).join('')}</ul>` : '');
    }

    function renderResults() {
        const searching = state.query.trim().length > 0;
        clearBtn.hidden = !state.query;
        resultsEl.setAttribute('aria-label', t(searching ? 'legend.searchResults' : 'legend.title'));
        resultsEl.innerHTML = searching ? renderSearch(state.query) : renderFacilities();
    }

    function scheduleAnnounce(text) {
        clearTimeout(announceTimer);
        announceTimer = setTimeout(() => {
            if (typeof announce === 'function') announce(text);
        }, 600);
    }

    // --- Panel-Modi --------------------------------------------------------

    function setHeader(mode, title) {
        titleEl.textContent = title;
        titleEl.style.color = '';
        backBtn.hidden = mode !== 'detail' || !state.fromLegend;
        panel.classList.toggle('is-legend', mode === 'legend');
        updateShareButton();
    }

    function openLegend() {
        hidePill();
        clearSpotlight();
        state.mode = 'legend';
        state.fromLegend = false;
        setHeader('legend', t('legend.title'));
        detailView.hidden = true;
        detailView.innerHTML = '';
        legendView.hidden = false;
        renderResults();
        document.body.classList.add('legend-open');
        const inst = bootstrap.Offcanvas.getOrCreateInstance(panel);
        if (panel.classList.contains('show')) body.scrollTop = state.scrollTop;
        else inst.show();
    }

    // Suche-Button an der Karte: Legende öffnen und direkt ins Suchfeld.
    // Auch auf dem Handy (sonst nur mit Maus/Trackpad) – hier will man tippen.
    function openSearch() {
        focusSearchOnShow = true;
        openLegend();
        if (panel.classList.contains('show')) {
            focusSearchOnShow = false;
            searchInput.focus({ preventScroll: true });
        }
    }

    function backToLegend() {
        state.mode = 'legend';
        state.fromLegend = false;
        setHeader('legend', t('legend.title'));
        detailView.hidden = true;
        detailView.innerHTML = '';
        legendView.hidden = false;
        renderResults();
        body.scrollTop = state.scrollTop;
        // Fokus zurück auf den Eintrag, der die Details geöffnet hat
        const last = state.detailId && resultsEl.querySelector(`[data-open="${CSS.escape(state.detailId)}"]`);
        (last || searchInput).focus({ preventScroll: true });
    }

    // Wird von openBuildingInfo() (main.js) gerufen, nachdem die Details
    // gerendert sind. fromLegend: Zurück-Knopf und „Auf Karte zeigen“ zeigen.
    function onDetailShown(id, fromLegend) {
        if (state.mode === 'legend' && !legendView.hidden) state.scrollTop = body.scrollTop;
        state.mode = 'detail';
        state.detailId = id;
        state.fromLegend = !!fromLegend;
        legendView.hidden = true;
        detailView.hidden = false;
        backBtn.hidden = !state.fromLegend;
        panel.classList.remove('is-legend');
        document.body.classList.toggle('legend-open', state.fromLegend);
        body.scrollTop = 0;
        if (state.fromLegend && mapElement(id)) {
            const bar = document.createElement('div');
            bar.className = 'building-actions';
            // Liegt das Ziel in einer ausgeblendeten Ebene, gibt es keinen
            // Umriss zum Ausschneiden – dann bleibt es beim einfachen Button
            bar.innerHTML = miniMap(id) || `<button type="button" class="show-on-map-btn" data-show-on-map="${id}">
                <i class="fas fa-map-marker-alt" aria-hidden="true"></i><span>${esc(t('legend.showOnMap'))}</span></button>`;
            detailView.prepend(bar);
        }
        updateShareButton();
    }

    // --- Teilen (Icon links neben „Schließen“) -----------------------------
    // Das Icon öffnet ein kleines Fenster mit dem Link. Kopiert wird erst
    // beim Klick ins Linkfeld oder aufs Kopier-Icon darin. Klappt das nicht
    // (fremdes iframe ohne Erlaubnis), bleibt der Link markiert stehen.
    let shareBtn, sharePop, shareReset;

    // Kurz und lesbar: Gebäudenummer (B.59, MFC1), sonst die ID (Kaffee_Cafeteria)
    function shareUrl(id) {
        const url = new URL(window.location.href);
        url.search = '';
        url.hash = '';
        url.pathname = url.pathname.replace(/index\.html$/, '');
        url.searchParams.set('show', buildingById(id)?.code.replace(/\s+/g, '') || id);
        if (CURRENT_LANG !== DEFAULT_LANG) url.searchParams.set('lang', CURRENT_LANG);
        return url.toString();
    }

    // Nur in den Gebäude-Infos, und nur wenn es den Ort auf der Karte gibt
    function updateShareButton() {
        closeSharePop();
        shareBtn.hidden = !(state.mode === 'detail' && state.detailId && mapElement(state.detailId));
    }

    // Hängt am Panel, nicht in der Kopfzeile: die ist auf dem Handy der Zieh-Griff
    function ensureSharePop() {
        if (sharePop) return sharePop;
        sharePop = document.createElement('div');
        sharePop.id = 'sharePop';
        sharePop.className = 'share-pop';
        sharePop.hidden = true;
        sharePop.setAttribute('role', 'dialog');
        sharePop.setAttribute('aria-label', t('share.title'));
        sharePop.innerHTML = `
          <p class="share-pop-status"></p>
          <div class="share-pop-field">
            <input class="share-pop-input" type="text" readonly aria-label="${esc(t('share.title'))}">
            <button type="button" class="share-pop-copy" aria-label="${esc(t('share.copy'))}" title="${esc(t('share.copy'))}">
              <i class="fas fa-copy" aria-hidden="true"></i></button>
          </div>`;
        const input = sharePop.querySelector('.share-pop-input');
        input.addEventListener('click', () => copyLink());
        input.addEventListener('focus', () => input.select());
        sharePop.querySelector('.share-pop-copy').addEventListener('click', () => copyLink());
        // direkt hinter der Kopfzeile: Tab führt vom Icon gleich hinein
        panel.querySelector('.offcanvas-header').after(sharePop);
        return sharePop;
    }

    function setShareStatus(mode) {
        const status = sharePop.querySelector('.share-pop-status');
        const icon = sharePop.querySelector('.share-pop-copy i');
        status.className = `share-pop-status is-${mode}`;
        status.innerHTML = mode === 'ok'
            ? `<i class="fas fa-check" aria-hidden="true"></i> ${esc(t('share.copied'))}`
            : esc(t(mode === 'failed' ? 'share.copyFailed' : 'share.title'));
        icon.className = mode === 'ok' ? 'fas fa-check' : 'fas fa-copy';
    }

    // Zwischenablage-API fehlt ohne https und ist in fremden iframes oft
    // gesperrt – dann der alte Weg über die markierte Eingabe
    async function copyLink() {
        const input = sharePop.querySelector('.share-pop-input');
        let ok = false;
        try {
            await navigator.clipboard.writeText(input.value);
            ok = true;
        } catch (e) {
            input.focus();
            input.select();
            try { ok = document.execCommand('copy'); } catch (e2) { }
        }
        setShareStatus(ok ? 'ok' : 'failed');
        if (typeof announce === 'function') announce(t(ok ? 'share.copied' : 'share.copyFailed'));
        clearTimeout(shareReset);
        if (ok) shareReset = setTimeout(() => setShareStatus('idle'), 2500);
    }

    function openSharePop() {
        const pop = ensureSharePop();
        pop.querySelector('.share-pop-input').value = shareUrl(state.detailId);
        clearTimeout(shareReset);
        setShareStatus('idle');
        pop.style.top = `${panel.querySelector('.offcanvas-header').offsetHeight}px`;
        pop.hidden = false;
        shareBtn.setAttribute('aria-expanded', 'true');
        // Fokus aufs Kopier-Icon: mit der Tastatur genügt dann Enter
        pop.querySelector('.share-pop-copy').focus({ preventScroll: true });
    }

    function closeSharePop(returnFocus) {
        if (!sharePop || sharePop.hidden) return;
        sharePop.hidden = true;
        shareBtn.setAttribute('aria-expanded', 'false');
        if (returnFocus) shareBtn.focus();
    }

    function bindShareEvents() {
        shareBtn.addEventListener('click', () => (sharePop && !sharePop.hidden ? closeSharePop() : openSharePop()));
        document.addEventListener('pointerdown', e => {
            if (sharePop && !sharePop.hidden && !sharePop.contains(e.target) && !shareBtn.contains(e.target)) closeSharePop();
        });
        // Escape schließt erst das kleine Fenster, nicht gleich das ganze Panel
        document.addEventListener('keydown', e => {
            if (e.key !== 'Escape' || !sharePop || sharePop.hidden) return;
            e.stopPropagation();
            closeSharePop(true);
        }, true);
        panel.addEventListener('hide.bs.offcanvas', () => closeSharePop());
    }

    function openDetail(id, trigger) {
        if (!contentOf(id)) return;
        state.scrollTop = body.scrollTop;
        openBuildingInfo(id, { fromLegend: true });
        // Fokus in die Details (Überschrift), damit Screenreader mitkommen
        if (trigger) titleEl.focus({ preventScroll: true });
    }

    // --- Karte: finden, einblenden, hinfliegen, hervorheben ----------------

    function mapSvg() {
        return document.querySelector('#lottieMap svg');
    }

    function mapElement(id) {
        const svg = mapSvg();
        return svg ? svg.querySelector(`#${CSS.escape(id)}`) : null;
    }

    // Liegt das Element in einer ausgeblendeten Ebene (Einstellungen),
    // wird die Ebene eingeschaltet – sonst gäbe es nichts zu zeigen.
    function ensureLayerVisible(el) {
        filters.forEach((f, i) => {
            const ids = Array.isArray(f.id) ? f.id : [f.id];
            const inLayer = ids.some(gid => document.getElementById(gid)?.contains(el));
            if (inLayer && filterState[filterKey(f)] === false) setFilterVisible(i, true);
        });
    }

    function setFilterVisible(index, visible) {
        const f = filters[index];
        if (!f) return;
        filterState[filterKey(f)] = visible;
        try { localStorage.setItem('filter_settings_v3', JSON.stringify(filterState)); } catch (e) { }
        const cb = document.getElementById(`filter-${index}`);
        if (cb) {
            cb.checked = visible;
            cb.closest('.filter-card')?.classList.toggle('active', visible);
        }
        window.updateFilterStyles();
        if (typeof updateToggleAllButton === 'function') updateToggleAllButton();
    }

    function spotlightLayer() {
        const svg = mapSvg();
        if (!svg) return null;
        let layer = svg.querySelector('#mapSpotlight');
        if (!layer) {
            layer = document.createElementNS('http://www.w3.org/2000/svg', 'g');
            layer.id = 'mapSpotlight';
            layer.setAttribute('pointer-events', 'none');
            layer.setAttribute('aria-hidden', 'true');
        }
        svg.appendChild(layer); // immer zuoberst
        return layer;
    }

    function colorFor(id) {
        const b = buildingById(id);
        if (b) return areaOf(b.area).color;
        const g = LEGEND_PLACE_GROUPS.find(g => [].concat(g.prefix).some(p => id.startsWith(p)));
        return g ? g.color : '#4b5459';
    }

    // Umriss eines Kartenelements in SVG-Koordinaten (unabhängig vom Zoom).
    // null, wenn es gerade nicht gezeichnet wird (ausgeblendete Ebene).
    function boxInSvg(el, pad) {
        const svg = mapSvg();
        const inv = svg?.getScreenCTM()?.inverse();
        if (!inv || !el) return null;
        const r = el.getBoundingClientRect();
        if (!r.width && !r.height) return null;
        const toSvg = (x, y) => {
            const p = svg.createSVGPoint();
            p.x = x; p.y = y;
            return p.matrixTransform(inv);
        };
        const a = toSvg(r.left, r.top);
        const b = toSvg(r.right, r.bottom);
        return {
            x: Math.min(a.x, b.x) - pad, y: Math.min(a.y, b.y) - pad,
            w: Math.abs(b.x - a.x) + pad * 2, h: Math.abs(b.y - a.y) + pad * 2
        };
    }

    function spotlightMarkup(box, id, mode) {
        const { x, y, w, h } = box;
        const ring = `<rect class="map-spotlight-ring" x="${x}" y="${y}" width="${w}" height="${h}" rx="10"/>`;
        const wave = mode === 'pulse' ? `<rect class="map-spotlight-wave" x="${x}" y="${y}" width="${w}" height="${h}" rx="10"/>` : '';
        return `<g class="map-spotlight is-${mode}" style="--spot:${colorFor(id)}">${wave}${ring}</g>`;
    }

    // mode: 'hover' (ruhiger Rahmen, nur solange die Maus drauf ist) oder
    // 'pulse' (bleibt stehen: nach „Auf Karte zeigen“ bzw. „Markieren“)
    function spotlight(ids, mode) {
        const svg = mapSvg();
        const layer = spotlightLayer();
        if (!svg || !layer) return;
        if (mode === 'hover') clearSpotlight(true);
        else layer.innerHTML = '';
        ids.forEach(id => {
            const box = boxInSvg(mapElement(id), 6);
            if (box) layer.insertAdjacentHTML('beforeend', spotlightMarkup(box, id, mode));
        });
    }

    // --- Mini-Lageplan in den Gebäude-Infos --------------------------------
    // Ausschnitt der echten Karte rund ums Gebäude. <use> zeigt die schon
    // geladenen Ebenen noch einmal an – nichts wird doppelt geladen, und der
    // Zoom der großen Karte (deren viewBox) wirkt sich hier nicht aus.
    const MINI_MAP_LAYERS = ['Hg', 'Bereiche', 'unbzeichnete_Flaechen', 'Parkplaetze', 'Straßen',
        'Carlebach_Park', 'Gebaeude', 'Gebaeudebezeichnung'];
    const MINI_MAP_RATIO = 2.6;   // Breite : Höhe, passt zu .mini-map-svg

    function miniMap(id) {
        const svg = mapSvg();
        const el = mapElement(id);
        const box = boxInSvg(el, 6);
        if (!box) return null;
        const layers = [...svg.children].filter(c => MINI_MAP_LAYERS.includes(c.id));
        // Ziel in einer anderen Ebene (Bushaltestelle, Fahrradstation …): die dazu
        const own = [...svg.children].find(c => c.contains(el));
        if (own && !layers.includes(own)) layers.push(own);

        // Ausschnitt: Gebäude mittig, Nachbarn drumherum, nicht über den Rand
        const full = { w: 1920, h: 1080 };   // viewBox der Karte ohne Zoom
        let w = Math.max(box.w * 5, 680);
        let h = Math.max(box.h * 3, w / MINI_MAP_RATIO);
        w = Math.min(full.w, Math.max(w, h * MINI_MAP_RATIO));
        h = Math.min(full.h, w / MINI_MAP_RATIO);
        const x = Math.min(full.w - w, Math.max(0, box.x + box.w / 2 - w / 2));
        const y = Math.min(full.h - h, Math.max(0, box.y + box.h / 2 - h / 2));

        const uses = layers.map(l => `<use href="#${esc(l.id)}"/>`).join('');
        return `<button type="button" class="mini-map" data-show-on-map="${id}">
            <svg class="mini-map-svg" viewBox="${x} ${y} ${w} ${h}" preserveAspectRatio="xMidYMid slice" aria-hidden="true" focusable="false">
              <defs><mask id="miniMapMask"><rect x="${x}" y="${y}" width="${w}" height="${h}" fill="#fff"/>
                <rect x="${box.x}" y="${box.y}" width="${box.w}" height="${box.h}" rx="10" fill="#000"/></mask></defs>
              ${uses}
              <rect x="${x}" y="${y}" width="${w}" height="${h}" fill="#fff" fill-opacity=".45" mask="url(#miniMapMask)"/>
              ${spotlightMarkup(box, id, 'pulse')}
            </svg>
            <span class="mini-map-hint"><i class="fas fa-expand-alt" aria-hidden="true"></i>${esc(t('legend.showOnMap'))}</span>
          </button>`;
    }

    function clearSpotlight(onlyHover) {
        const layer = mapSvg()?.querySelector('#mapSpotlight');
        if (!layer) return;
        if (onlyHover) layer.querySelectorAll('.map-spotlight.is-hover').forEach(n => n.remove());
        else layer.innerHTML = '';
    }

    function visibleMapRegion(excludePanel) {
        const header = document.getElementById('allcontent-title');
        const top = header ? header.getBoundingClientRect().bottom : 0;
        let right = window.innerWidth;
        if (excludePanel && panel.classList.contains('show')) right = panel.getBoundingClientRect().left;
        const bottom = window.innerHeight - (pill && !pill.hidden ? pill.offsetHeight + 24 : 0);
        return { left: 0, top, width: right, height: Math.max(100, bottom - top) };
    }

    function flyTo(id) {
        const el = mapElement(id);
        const zoom = window.mapZoomControls;
        if (!el || !zoom?.flyToElement) return;
        const done = () => spotlight([id], 'pulse');
        zoom.flyToElement(el, {
            region: visibleMapRegion(true),
            zoom: isSheet() ? 2.6 : 1.8,
            animate: typeof areAnimationsEnabled === 'function' ? areAnimationsEnabled() : true
        }).then(done);
    }

    function showOnMap(id) {
        const el = mapElement(id);
        if (!el) return;
        ensureLayerVisible(el);
        // Deckt das Panel den Großteil der Karte ab (Smartphone, Tablet hoch),
        // geht es zu – die Leiste unten führt zurück zu den Infos.
        if (panelCoversMap()) {
            pendingAction = () => {
                showPill({ title: contentOf(id)?.title || '', action: t('legend.pillInfo'), color: colorFor(id),
                    open: () => openBuildingInfo(id, { fromLegend: true }) });
                flyTo(id);
            };
            bootstrap.Offcanvas.getOrCreateInstance(panel).hide();
        } else {
            showPill({ title: contentOf(id)?.title || '', action: t('legend.pillInfo'), color: colorFor(id),
                open: () => openBuildingInfo(id, { fromLegend: true }) });
            flyTo(id);
        }
    }

    function panelCoversMap() {
        return panel.offsetWidth > window.innerWidth * 0.55;
    }

    // Mehrere Orte auf einmal markieren, ohne den Kartenausschnitt zu ändern
    function markOnMap(ids, title) {
        ids.map(mapElement).filter(Boolean).forEach(ensureLayerVisible);
        if (panelCoversMap()) {
            pendingAction = () => {
                showPill({ title, action: t('legend.pillMarked', { n: ids.length }), color: colorFor(ids[0]), open: openLegend });
                spotlight(ids, 'pulse');
            };
            bootstrap.Offcanvas.getOrCreateInstance(panel).hide();
        } else {
            showPill({ title, action: t('legend.pillMarked', { n: ids.length }), color: colorFor(ids[0]), open: openLegend });
            spotlight(ids, 'pulse');
        }
    }

    // --- Leiste „zurück zu den Infos“ (nach „Auf Karte zeigen“) -------------

    function ensurePill() {
        if (pill) return pill;
        pill = document.createElement('div');
        pill.className = 'map-return-pill';
        pill.hidden = true;
        pill.innerHTML = `
          <button type="button" class="map-return-main">
            <span class="map-return-dot" aria-hidden="true"></span>
            <span class="map-return-text"><span class="map-return-name"></span>
              <span class="map-return-action"></span></span>
            <i class="fas fa-chevron-up" aria-hidden="true"></i>
          </button>
          <button type="button" class="map-return-close" aria-label="${esc(t('legend.pillClose'))}">
            <i class="fas fa-times" aria-hidden="true"></i>
          </button>`;
        pill.querySelector('.map-return-main').addEventListener('click', () => {
            const open = pillOpen;
            hidePill();
            clearSpotlight();
            if (open) open();
        });
        pill.querySelector('.map-return-close').addEventListener('click', () => {
            hidePill();
            clearSpotlight();
            document.querySelector('[data-map-search]')?.focus();
        });
        document.body.appendChild(pill);
        return pill;
    }

    function showPill({ title, action, color, open }) {
        const p = ensurePill();
        pillOpen = open;
        p.style.setProperty('--spot', color);
        p.querySelector('.map-return-name').textContent = title;
        p.querySelector('.map-return-action').textContent = action;
        p.hidden = false;
        document.body.classList.add('map-pill-open');
    }

    function hidePill() {
        if (!pill || pill.hidden) return;
        pill.hidden = true;
        document.body.classList.remove('map-pill-open');
    }

    // --- Bottom-Sheet: nach unten ziehen zum Schließen ----------------------

    function enableSheetDrag() {
        const header = panel.querySelector('.offcanvas-header');
        let startY = null, dy = 0, startT = 0;
        header.addEventListener('touchstart', e => {
            if (!isSheet() || e.target.closest('button')) return;
            startY = e.touches[0].clientY;
            startT = performance.now();
            dy = 0;
            panel.style.transition = 'none';
        }, { passive: true });
        header.addEventListener('touchmove', e => {
            if (startY === null) return;
            dy = Math.max(0, e.touches[0].clientY - startY);
            panel.style.transform = `translateY(${dy}px)`;
        }, { passive: true });
        const end = () => {
            if (startY === null) return;
            const fast = dy > 40 && dy / (performance.now() - startT) > 0.5;
            startY = null;
            panel.style.transition = '';
            panel.style.transform = '';
            if (dy > 110 || fast) bootstrap.Offcanvas.getOrCreateInstance(panel).hide();
        };
        header.addEventListener('touchend', end);
        header.addEventListener('touchcancel', end);
    }

    // --- Ereignisse --------------------------------------------------------

    function bindEvents() {
        backBtn.addEventListener('click', backToLegend);

        searchInput.addEventListener('input', () => {
            state.query = searchInput.value;
            renderResults();
            body.scrollTop = 0;
        });
        searchInput.addEventListener('keydown', e => {
            if (e.key === 'Escape' && searchInput.value) {
                e.stopPropagation(); // Panel bleibt offen, nur die Suche wird geleert
                searchInput.value = '';
                state.query = '';
                renderResults();
            } else if (e.key === 'Enter') {
                // Enter öffnet den ersten Treffer
                const first = resultsEl.querySelector('[data-open]');
                if (state.query.trim() && first) {
                    e.preventDefault();
                    searchInput.blur();
                    openDetail(first.dataset.open, true);
                }
            }
        });
        clearBtn.addEventListener('click', () => {
            searchInput.value = '';
            state.query = '';
            renderResults();
            searchInput.focus();
        });

        // Leertaste öffnet die Suche – aber nur, wenn sie gerade nichts anderes
        // tut: kein Eingabefeld, Button, Link oder Kartenelement im Fokus und
        // kein Quiz, Einstellungs- oder Badges-Fenster offen.
        document.addEventListener('keydown', e => {
            if (e.key !== ' ' || e.repeat || e.ctrlKey || e.metaKey || e.altKey || e.defaultPrevented) return;
            if (e.target.closest?.('input, textarea, select, button, a, [contenteditable], [tabindex]:not(#mapContainer), .modal, .offcanvas')) return;
            if (document.querySelector('.modal.show, .offcanvas.show:not(#buildingInfoOffcanvas)')) return;
            e.preventDefault();
            openSearch();
        });

        resultsEl.addEventListener('click', e => {
            const pinBtn = e.target.closest('[data-pin]');
            if (pinBtn) {
                showOnMap(pinBtn.dataset.pin);
                return;
            }
            const markBtn = e.target.closest('[data-mark]');
            if (markBtn) {
                markOnMap(markBtn.dataset.mark.split(' '), markBtn.querySelector('.legend-row-name').textContent.trim());
                return;
            }
            const btn = e.target.closest('[data-open]');
            if (btn) openDetail(btn.dataset.open, e.detail === 0);
        });
        detailView.addEventListener('click', e => {
            const btn = e.target.closest('[data-show-on-map]');
            if (btn) showOnMap(btn.dataset.showOnMap);
        });

        // Hover/Fokus: Gebäude auf der Karte mit aufleuchten lassen (Desktop)
        const highlightFrom = target => {
            const el = target.closest && target.closest('[data-highlight]');
            if (!el) return null;
            // Chip in einer Mehrfach-Zeile: nur dieses Gebäude
            return el.dataset.highlight.split(' ').filter(Boolean);
        };
        resultsEl.addEventListener('pointerover', e => {
            if (e.pointerType !== 'mouse' || !canHover()) return;
            const ids = highlightFrom(e.target);
            if (ids) spotlight(ids, 'hover'); else clearSpotlight(true);
        });
        resultsEl.addEventListener('pointerleave', () => clearSpotlight(true));
        resultsEl.addEventListener('focusin', e => {
            if (!canHover()) return;
            const ids = highlightFrom(e.target);
            if (ids) spotlight(ids, 'hover');
        });
        resultsEl.addEventListener('focusout', () => clearSpotlight(true));

        panel.addEventListener('shown.bs.offcanvas', () => {
            if (state.mode === 'legend' && !legendView.hidden) {
                body.scrollTop = state.scrollTop;
                // Tastatur nur auf Geräten mit Maus/Trackpad direkt in die Suche –
                // auf dem Handy würde sonst sofort die Tastatur das Sheet verdecken
                if (focusSearchOnShow || window.matchMedia('(pointer: fine)').matches) searchInput.focus({ preventScroll: true });
                focusSearchOnShow = false;
            }
        });
        panel.addEventListener('hide.bs.offcanvas', () => {
            if (state.mode === 'legend' && !legendView.hidden) state.scrollTop = body.scrollTop;
        });
        panel.addEventListener('hidden.bs.offcanvas', () => {
            document.body.classList.remove('legend-open');
            if (pendingAction) {
                const action = pendingAction;
                pendingAction = null;
                action();
                pill.querySelector('.map-return-main').focus({ preventScroll: true });
            } else if (!pill || pill.hidden) {
                // Die Markierung bleibt, solange die Leiste unten sie noch trägt
                clearSpotlight();
            }
            state.mode = 'closed';
        });
        panel.addEventListener('show.bs.offcanvas', () => hidePill());

        enableSheetDrag();
    }

    // --- Direktlinks: ?show=… (Karte) und ?info=… (Gebäude-Infos) ---------
    // Als Ziel geht: interne ID (Mensa_B_59), neue oder alte Gebäudenummer
    // (B.59, b59, 36), Name (Mensa, Bibliothek) oder Einrichtung
    // (International Office). Schreibweise und Satzzeichen sind egal, Tippfehler
    // werden aber bewusst nicht geraten – ein Link soll eindeutig sein.
    function resolveTarget(raw) {
        const c = compact(raw || '');
        if (!c) return null;
        const single = id => ({ ids: [id], title: contentOf(id)?.title || id });
        const byId = campusBuildings.find(b => compact(b.id) === c);
        if (byId) return single(byId.id);
        const bld = LEGEND_BUILDINGS.find(b => compact(b.code) === c || b.old === c
            || (b.name && [b.name.de, b.name.en].some(n => compact(n) === c)));
        if (bld && contentOf(bld.id)) return single(bld.id);
        const byTitle = campusBuildings.find(b => compact(b.title) === c);
        if (byTitle) return single(byTitle.id);
        const fac = LEGEND_FACILITIES.find(f => [f.de, f.en].some(n => compact(n) === c));
        if (!fac) return null;
        const ids = fac.mark || fac.in.map(buildingByCode).filter(b => b && contentOf(b.id)).map(b => b.id);
        // Leiste zeigt den gesuchten Namen („International Office“), nicht „Gebäude A.1“
        return ids.length ? { ids, title: L(fac), stations: !!fac.mark } : null;
    }

    // Läuft einmal, sobald die Karte steht (main.js überspringt dann das Intro)
    function openFromUrl() {
        const params = new URLSearchParams(window.location.search);
        const raw = params.get('info') || params.get('show');
        const target = resolveTarget(raw);
        if (!target) {
            if (raw) console.warn(`Campusplan: Ziel „${raw}“ nicht gefunden`);
            return;
        }
        const { ids, title } = target;
        ids.map(mapElement).filter(Boolean).forEach(ensureLayerVisible);

        if (params.get('info') && ids.length === 1) {
            // Infos öffnen; wo daneben Platz ist, fliegt die Karte mit hin
            panel.addEventListener('shown.bs.offcanvas', () => { if (!panelCoversMap()) flyTo(ids[0]); }, { once: true });
            openBuildingInfo(ids[0], { fromLegend: true });
        } else if (ids.length === 1) {
            showPill({ title, action: t('legend.pillInfo'), color: colorFor(ids[0]),
                open: () => openBuildingInfo(ids[0], { fromLegend: true }) });
            flyTo(ids[0]);
        } else {
            const action = t(target.stations ? 'legend.pillMarked' : 'legend.pillMarkedPlaces', { n: ids.length });
            showPill({ title, action, color: colorFor(ids[0]), open: openLegend });
            spotlight(ids, 'pulse');
        }
    }

    function init() {
        panel = document.getElementById('buildingInfoOffcanvas');
        if (!panel) return;
        body = panel.querySelector('.offcanvas-body');
        legendView = document.getElementById('legendView');
        detailView = document.getElementById('buildingInfoContent');
        titleEl = document.getElementById('buildingInfoLabel');
        backBtn = document.getElementById('buildingInfoBack');
        searchInput = document.getElementById('legendSearch');
        clearBtn = document.getElementById('legendSearchClear');
        resultsEl = document.getElementById('legendResults');
        shareBtn = document.getElementById('buildingInfoShare');
        titleEl.tabIndex = -1;
        bindEvents();
        bindShareEvents();
        renderResults();
    }

    return { init, open: openLegend, openSearch, onDetailShown, showOnMap, openFromUrl, resolveTarget };
})();

window.campusLegend = campusLegend;
document.addEventListener('DOMContentLoaded', () => campusLegend.init());

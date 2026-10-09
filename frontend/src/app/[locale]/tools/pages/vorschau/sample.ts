import type { Block, Limits, Page } from "../_lib/types";

// Temporary sample data for the preview of all looks, the same content as the approved gallery.

export const LIMITS: Limits = {
  sections: 20, blocks: 4, images: 10, tableRows: 12, tableCols: 6, items: 10, short: 120, item: 300,
  long: 1500, imagePrompt: 1500, series: 2, branches: 8, leaves: 5, words: 24, label: 24, mapLabel: 40,
};

const steps = [
  { title: "Einreichung", text: "Der Wunsch wird mit einer Begründung schriftlich eingereicht." },
  { title: "Prüfung", text: "Die Projektleitung prüft die Auswirkungen auf Leistung, Termine, Kosten und Risiken." },
  { title: "Entscheidung", text: "Der Auftraggeber entscheidet über die Änderung." },
  { title: "Anpassung", text: "Auftrag, Strukturplan, Terminplan und Budget werden angepasst." },
  { title: "Dokumentation", text: "Die Entscheidung wird mitgeteilt und in der Änderungsliste festgehalten." },
];

/** One sample per kind, each drawn in every look it has. */
export const SAMPLES: Block[] = [
  { kind: "text", text: "Der Projektstrukturplan zerlegt das Vorhaben in Einheiten, die beauftragt und abgerechnet werden können, wobei er nur das Was, nicht das Wann beantwortet. Gliederungsprinzipien sind objektorientiert, funktionsorientiert, phasenorientiert oder gemischt. Die kleinste Einheit ist das Arbeitspaket mit einer idealen Größe von 8 bis 80 Stunden. Erst auf dieser Ebene lassen sich Aufwand, Dauer und Verantwortung sauber zuordnen." },
  { kind: "bullets", items: [
    "Rückwärtsrechnen, bei dem die Schätzung passend gebogen wird.",
    "Kürzen von Schätzungen ohne gleichzeitige Verringerung des Umfangs.",
    "Vergessen von Abstimmungszeiten, Nacharbeiten, Urlaub, Krankheit und Feiertagen.",
    "Fälschliche Annahme einer 100 Prozent Verfügbarkeit der Mitarbeitenden.",
    "Fehlende Anpassung der Schätzung nach der ersten Version.",
  ] },
  { kind: "bullets", items: ["DIN 69901", "ISO 21500", "PMBOK", "PRINCE2", "IPMA ICB", "Scrum"] },
  { kind: "quote", text: "Der Projektstrukturplan beantwortet das Was, nicht das Wann.", keyword: "Projektstrukturplan" },
  { kind: "checklist", items: ["Ausgangslage", "Ziele", "Nichtziele", "Termine", "Budget", "Rollen", "Unterschriften"] },
  { kind: "definitions", items: [
    { term: "Projekt", text: "Ein einmaliges Vorhaben mit Ziel, Anfang, Ende und begrenzten Mitteln." },
    { term: "Arbeitspaket", text: "Die kleinste Einheit des Strukturplans, ideal 8 bis 80 Stunden groß." },
    { term: "Meilenstein", text: "Ein Zwischenstand, an dem der Fortschritt geprüft wird." },
    { term: "Stakeholder", text: "Personen oder Organisationen, deren Interessen das Projekt berührt." },
    { term: "Nichtziel", text: "Was ausdrücklich nicht dazugehört, damit der Umfang nicht wächst." },
  ] },
  { kind: "cards", cards: [
    { icon: "x", title: "Vermeiden", text: "Die Ursache wird beseitigt oder es wird notfalls auf etwas verzichtet." },
    { icon: "warning", title: "Vermindern", text: "Die Wahrscheinlichkeit oder die Auswirkung wird gesenkt." },
    { icon: "idea", title: "Übertragen", text: "Das Risiko wird durch Versicherungen, Festpreise oder Vertragsstrafen einem Dritten gegeben." },
    { icon: "check", title: "Tragen", text: "Das Risiko wird bewusst hingenommen und mit einer finanziellen Rücklage hinterlegt." },
    { icon: "none", title: "Beobachten", text: "Das Risiko bleibt auf der Liste und wird in jeder Sitzung neu bewertet." },
  ] },
  { kind: "accordion", items: [
    { title: "Expertenschätzung", text: "Eine erfahrene Person nennt ihre Zahl. Das geht schnell, hängt aber an einer einzigen Einschätzung und ihrer Tagesform." },
    { title: "Analogieschätzung", text: "Das Vorhaben wird mit früheren, ähnlichen Projekten verglichen. Sie trägt nur, wenn die Unterschiede bekannt und klein sind." },
    { title: "Kennzahlenschätzung", text: "Der Aufwand je Einheit wird mit der Menge multipliziert, etwa Stunden je Seite mal Seitenzahl." },
    { title: "Drei-Zeiten-Schätzung", text: "Aus optimistischem, wahrscheinlichem und pessimistischem Wert ergibt sich ein gewichteter Erwartungswert." },
    { title: "Schätzklausur", text: "Mehrere Personen schätzen verdeckt, danach werden große Abweichungen besprochen und neu geschätzt." },
  ] },
  { kind: "steps", steps },
  { kind: "steps", steps: steps.slice(0, 3) },
  { kind: "steps", steps: [...steps, { title: "Nachkontrolle", text: "Nach vier Wochen wird geprüft, ob die Änderung wirkt." }, { title: "Abschluss", text: "Der Antrag wird geschlossen." }] },
  { kind: "cycle", center: "PDCA-Zyklus", steps: [
    { title: "Plan", text: "Ziele festlegen und Maßnahmen planen." },
    { title: "Do", text: "Maßnahmen im kleinen Rahmen umsetzen." },
    { title: "Check", text: "Ergebnisse mit den Zielen vergleichen." },
    { title: "Act", text: "Bewährtes zum Standard machen, sonst neu planen." },
  ] },
  { kind: "timeline", events: [
    { date: "1957", title: "Netzplantechnik", text: "Mit CPM entsteht die Methode des kritischen Pfads." },
    { date: "1969", title: "PMI gegründet", text: "Das Project Management Institute nimmt die Arbeit auf." },
    { date: "1989", title: "PRINCE", text: "Die britische Regierung führt PRINCE als Standard ein." },
    { date: "1996", title: "PMBOK Guide", text: "Der erste PMBOK Guide fasst das Wissen zusammen." },
    { date: "2001", title: "Agiles Manifest", text: "Siebzehn Entwickler formulieren vier Werte agiler Arbeit." },
    { date: "2012", title: "ISO 21500", text: "Ein internationaler Leitfaden für Projektmanagement erscheint." },
  ] },
  { kind: "tree", root: "Neubau Kita", branches: [
    { title: "Planung", leaves: ["Entwurf", "Genehmigung", "Ausschreibung"] },
    { title: "Rohbau", leaves: ["Fundament", "Mauerwerk", "Dach"] },
    { title: "Ausbau", leaves: ["Elektrik", "Sanitär", "Innenausbau"] },
    { title: "Außenanlage", leaves: ["Spielplatz", "Wege"] },
  ] },
  { kind: "levels", caption: "Ebenen der Projektorganisation", items: [
    { title: "Lenkungsausschuss", text: "Entscheidet über Ziele, Budget und Abbruch." },
    { title: "Projektleitung", text: "Plant, steuert und berichtet." },
    { title: "Teilprojektleitung", text: "Verantwortet einen Teil des Strukturplans." },
    { title: "Projektteam", text: "Bearbeitet die Arbeitspakete." },
  ] },
  { kind: "figures", figures: [
    { value: "8–80 Std.", label: "ideale Größe eines Arbeitspakets" },
    { value: "1–5", label: "Skala für Wahrscheinlichkeit und Auswirkung" },
    { value: "< 1", label: "SPI oder CPI zeigt Verzug oder Mehrkosten" },
    { value: "4", label: "Strategien im Umgang mit Risiken" },
  ] },
  { kind: "bars", max: 100, bars: [
    { label: "Null-zu-100-Regel", value: 0, text: "Leistung zählt erst bei Abschluss." },
    { label: "50-zu-50-Regel", value: 50, text: "Die Hälfte wird beim Beginn verbucht." },
    { label: "Meilenstein-Technik", value: 60, text: "Zwei von drei Meilensteinen erreicht, gewichtet." },
    { label: "Mengenproportional", value: 72, text: "72 von 100 Einheiten erledigt." },
  ] },
  { kind: "chart", chart_type: "line", caption: "Plan- und Fertigstellungswert eines Projekts über sechs Monate", x_label: "Monat", y_label: "Tsd. €",
    categories: ["Jan", "Feb", "Mär", "Apr", "Mai", "Jun"],
    series: [{ name: "Planwert (PV)", values: [20, 45, 70, 100, 130, 160] }, { name: "Fertigstellungswert (EV)", values: [18, 40, 58, 82, 105, 128] }] },
  { kind: "chart", chart_type: "bar", caption: "Fertigstellungswert je Monat", x_label: "Monat", y_label: "Tsd. €",
    categories: ["Jan", "Feb", "Mär", "Apr", "Mai", "Jun"], series: [{ name: "", values: [18, 40, 58, 82, 105, 128] }] },
  { kind: "chart", chart_type: "pie", caption: "Verteilung des Aufwands auf die Projektphasen", x_label: "", y_label: "%",
    categories: ["Initiierung", "Planung", "Durchführung", "Steuerung", "Abschluss"], series: [{ name: "", values: [10, 25, 45, 12, 8] }] },
  { kind: "table", caption: "Verfahren der Aufwandsschätzung im Vergleich", header: ["Verfahren", "Grundlage", "Genauigkeit", "Aufwand"], rows: [
    ["Expertenschätzung", "Erfahrung einer Person", "mittel", "gering"],
    ["Analogieschätzung", "Frühere Vorhaben", "mittel", "gering"],
    ["Kennzahlenschätzung", "Aufwand je Einheit mal Menge", "hoch", "mittel"],
    ["Drei-Zeiten-Schätzung", "Optimistisch, wahrscheinlich, pessimistisch", "hoch", "mittel"],
    ["Schätzklausur", "Verdeckte Schätzungen mehrerer Personen", "sehr hoch", "hoch"],
  ] },
  { kind: "table", caption: "Schätzungen in Tagen", header: ["Arbeitspaket", "Optimistisch", "Wahrscheinlich", "Pessimistisch"], rows: [
    ["Migration", "4", "6", "14"], ["Schulung", "2", "3", "5"], ["Test", "3", "5", "9"],
  ] },
  { kind: "scale", caption: "Regeln der Fortschrittsmessung zwischen vorsichtig und genau", left: "vorsichtig", right: "genau", items: [
    { label: "Null-zu-100", pos: 0.08 }, { label: "50-zu-50", pos: 0.38 }, { label: "Meilensteine", pos: 0.62 }, { label: "Mengenproportional", pos: 0.92 },
  ] },
  { kind: "versus", tone: "neutral",
    a: { title: "Projektmanagement", items: ["Einmaliges Vorhaben", "Fester Anfang und festes Ende", "Eigenes Team auf Zeit", "Ziel ist ein neues Ergebnis"] },
    b: { title: "Prozessmanagement", items: ["Wiederkehrende Abläufe", "Läuft dauerhaft weiter", "Feste Linienorganisation", "Ziel ist ein stabiler Ablauf"] } },
  { kind: "versus", tone: "good_bad",
    a: { title: "Fördert den Erfolg", items: ["Klare Projektgrenzen", "Prozessorientierte Strukturen", "Commitment der Stakeholder", "Kompetente Personen"] },
    b: { title: "Gefährdet den Erfolg", items: ["Ignorierter Widerstand", "Mangelnde Akzeptanz", "Unklare Rollen"] } },
  { kind: "matrix", x: "Interesse", y: "Einfluss", cells: [
    { pos: "tl", title: "Zufriedenstellen", text: "Hoher Einfluss, geringes Interesse." },
    { pos: "tr", title: "Eng einbinden", text: "Hoher Einfluss, hohes Interesse." },
    { pos: "bl", title: "Beobachten", text: "Geringer Einfluss, geringes Interesse." },
    { pos: "br", title: "Informieren", text: "Geringer Einfluss, hohes Interesse." },
  ], points: [
    { label: "Auftraggeber", x: 0.85, y: 0.9 }, { label: "Behörde", x: 0.25, y: 0.8 }, { label: "Endkunden", x: 0.75, y: 0.3 },
    { label: "Gewerkschaft", x: 0.3, y: 0.35 }, { label: "Projektteam", x: 0.9, y: 0.6 },
  ] },
  { kind: "venn", a: { title: "Projekt", items: ["einmalig", "befristet"] }, b: { title: "Prozess", items: ["wiederkehrend", "dauerhaft"] },
    both: ["Ziele", "Ressourcen", "Steuerung"], c: { title: "Programm", items: ["mehrere Projekte"] } },
  { kind: "venn", a: { title: "Projekt", items: ["einmalig", "befristet"] }, b: { title: "Prozess", items: ["wiederkehrend", "dauerhaft"] },
    both: ["Ziele", "Ressourcen", "Steuerung"] },
  { kind: "formula", key: "E = (O + 4M + P) / 6", text: "Der erwartete Aufwand der Drei-Zeiten-Schätzung gewichtet den wahrscheinlichen Wert vierfach.",
    parts: [{ sym: "E", text: "erwarteter Aufwand" }, { sym: "O", text: "optimistischer Wert" }, { sym: "M", text: "wahrscheinlichster Wert" }, { sym: "P", text: "pessimistischer Wert" }],
    example: ["O = 4, M = 6, P = 14 Tage", "E = (4 + 4 · 6 + 14) / 6", "E = 42 / 6 = 7 Tage"] },
  { kind: "mistakes", pairs: [
    { wrong: "Die Schätzung wird gekürzt, der Umfang bleibt.", right: "Wer kürzt, streicht auch Umfang." },
    { wrong: "Mitarbeitende sind zu 100 Prozent verfügbar.", right: "Urlaub, Krankheit und Abstimmung abziehen." },
    { wrong: "Aufwand und Dauer sind dasselbe.", right: "Aufwand ist Arbeitszeit, Dauer ist verstrichene Zeit." },
    { wrong: "Prozentangaben zeigen den Fortschritt.", right: "Fortschritt an Meilensteinen oder Mengen messen." },
  ] },
  { kind: "example", title: "Drei-Zeiten-Schätzung für ein Arbeitspaket", situation: "Ein Team schätzt das Arbeitspaket Datenmigration.",
    steps: ["Optimistisch 4 Tage, wahrscheinlich 6 Tage, pessimistisch 14 Tage.", "Erwartung: (4 + 4 · 6 + 14) / 6."],
    result: "Geplant werden 7 Tage, nicht die 6 Tage des Bauchgefühls." },
  { kind: "highlight", key: "Risikowert", text: "Eintrittswahrscheinlichkeit mal Auswirkung auf einer Skala von 1 bis 5" },
  { kind: "highlight", key: "R = W × A", text: "Der Risikowert ist Eintrittswahrscheinlichkeit mal Auswirkung." },
  { kind: "image", src: "img_1.webp", alt: "Ein Team plant ein Projekt", prompt: "", caption: "Planung im Team" },
  { kind: "mindmap", center: "Projektmanagement", caption: "Das Thema auf einer Karte", branches: [
    { title: "Projektstart", to: "", leaves: ["Projektauftrag", "Kick-Off"] },
    { title: "Stakeholder", to: "", leaves: ["aktiv", "passiv"] },
    { title: "Struktur", to: "", leaves: ["Strukturplan", "Arbeitspaket"] },
    { title: "Steuerung", to: "", leaves: ["SPI", "CPI"] },
    { title: "Risiken", to: "", leaves: ["Risikowert", "Strategien"] },
    { title: "Widerstände", to: "", leaves: ["Akzeptanz", "Ursachen"] },
  ] },
  { kind: "wordcloud", caption: "Wörter, die immer wieder fallen", words: [
    ["Projekt", 48], ["Risiko", 31], ["Arbeitspaket", 22], ["Stakeholder", 20], ["Budget", 18],
    ["Meilenstein", 15], ["Strukturplan", 14], ["Schätzung", 13], ["Auftraggeber", 12], ["Ziele", 11],
    ["Steuerung", 10], ["Kick-Off", 8], ["Widerstand", 8], ["SPI", 6], ["CPI", 6], ["Nichtziele", 5],
  ] },
];

const by = (k: Block["kind"], n = 0) => SAMPLES.filter((b) => b.kind === k)[n];

/** A whole page to see how sections are built in each design. */
export function samplePage(design: Page["design"]): Page {
  const sec = (id: string, title: string, lead: string, blocks: Block[]) => ({ id, title, lead, blocks });
  return {
    version: 1, lang: "de", design, footer: "",
    sections: [
      sec("cover", "", "", [{ kind: "image", src: "img_0.webp", alt: "", prompt: "", caption: "" }]),
      { id: "top", hero: true, title: "Grundlagen und Steuerung im Projektmanagement", lead: "Diese Seite vermittelt die theoretischen Grundlagen sowie die Planung und operative Steuerung von Projekten.", meta: "Erstellt mit KI am 09.10.2026, etwa 6 Min. Lesezeit", blocks: [] },
      sec("gist", "Das Wichtigste in Kürze", "", [by("bullets"), by("formula")]),
      sec("map", "Das Thema auf einer Karte", "Klicke auf einen Ast, um zum Abschnitt zu springen.", [by("mindmap")]),
      sec("s1", "Konzepte und Definitionen", "Projektmanagement nutzt spezifische Methoden und Standards.", [by("text"), by("definitions")]),
      sec("s2", "Projektstart und Zieldefinition", "Der formelle Start erfolgt durch Projektauftrag und Kick-Off.", [by("checklist"), by("steps")]),
      sec("s3", "Anspruchsgruppen", "Stakeholder sind von den Interessen des Projekts betroffen.", [by("matrix")]),
      sec("s4", "Der Kern in einem Satz", "Was man sich merken sollte.", [by("quote")]),
      sec("s5", "Aufwand und Dauer", "Zwei Größen, die oft verwechselt werden.", [by("mistakes")]),
      sec("s6", "Schätzverfahren", "Fünf Wege zu einer Zahl.", [by("accordion"), by("table")]),
      sec("s7", "Planung im Team", "Gute Planung entsteht gemeinsam.", [by("image"), { kind: "text", text: "Ein Kick-Off bringt alle Beteiligten an einen Tisch. Ziele, Nichtziele und Rollen werden dort gemeinsam besprochen und festgehalten." }]),
      sec("s8", "Fortschritt messen", "Zahlen statt Bauchgefühl.", [by("chart"), by("figures")]),
      sec("s9", "Erfolgsfaktoren", "Was trägt, was bremst.", [by("versus", 1)]),
      sec("s10", "Geschichte", "Wie das Fach entstand.", [by("timeline")]),
      sec("words", "Wörter, die immer wieder fallen", "", [by("wordcloud")]),
    ],
  };
}

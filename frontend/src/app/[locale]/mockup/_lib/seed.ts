import type { MockupConfig, Station } from "./types";

const station = (
  id: string,
  icon: Station["icon"],
  de: [string, string, string],
  en: [string, string, string],
): Station => ({
  id,
  icon,
  name: { de: de[0], en: en[0] },
  blurb: { de: de[1], en: en[1] },
  francis: { de: de[2], en: en[2] },
});

export const SEED_CONFIG: MockupConfig = {
  masterCode: "K7PM",
  stations: [
    station(
      "francis",
      "francis",
      ["KI-Assistent Francis", "Fragen an deine Unterlagen stellen", "Francis antwortet aus deinen Quellen und nennt sie dazu."],
      ["AI assistant Francis", "Ask questions about your materials", "Francis answers from your sources and names them."],
    ),
    station(
      "translation",
      "translation",
      ["Übersetzung", "Texte und Dokumente übersetzen", "Probiere eine Übersetzung mit einem eigenen Text aus."],
      ["Translation", "Translate texts and documents", "Try a translation with a text of your own."],
    ),
    station(
      "tts",
      "tts",
      ["Text in Audio", "Texte vorlesen lassen", "Lass dir einen Abschnitt aus deinem Skript vorlesen."],
      ["Text to audio", "Have texts read aloud", "Have a section of your script read aloud."],
    ),
    station(
      "transcription",
      "transcription",
      ["Audio in Text", "Vorlesungen transkribieren", "Aus einer Aufnahme wird ein Text mit Zeitmarken."],
      ["Audio to text", "Transcribe lectures", "A recording becomes a text with timestamps."],
    ),
    station(
      "interpreter",
      "interpreter",
      ["Dolmetscher", "Ein Gespräch in zwei Sprachen", "Sprich in deiner Sprache, die Übersetzung läuft mit."],
      ["Interpreter", "A conversation in two languages", "Speak in your language, the translation follows along."],
    ),
    station(
      "summary",
      "summary",
      ["Zusammenfassung", "Mehrere Materialien in einem Text", "Aus mehreren Quellen entsteht ein kurzer Überblick."],
      ["Summary", "Several materials in one text", "Several sources become a short overview."],
    ),
  ],
  eventBlock: {
    enabled: true,
    ignoreWindow: true,
    from: "2026-11-06",
    until: "2026-11-13",
    heading: { de: "Tag der Lehre am 13.11.2026", en: "Day of Teaching on 13 November 2026" },
    text: {
      de: "KIS wird vorgestellt. Probiere es direkt aus oder sammle Stempel an allen Ständen.",
      en: "KIS is presented. Try it right away or collect stamps at all stands.",
    },
    tiles: [
      {
        id: "demo",
        icon: "francis",
        title: { de: "Demozugang", en: "Demo access" },
        body: { de: "Mit einem Klick in KIS und selbst ausprobieren.", en: "One click into KIS to try it yourself." },
        button: { de: "Ausprobieren", en: "Try it" },
        target: { kind: "directLogin", accessCode: "KIS-DEMO-0000" },
        active: false,
        availableFrom: "2026-11-13",
      },
      {
        id: "stamp",
        icon: "star",
        title: { de: "Stempelkarte", en: "Stamp card" },
        body: {
          de: "Besuche alle Stände, sammle Stempel und hol dir am Ende dein Geschenk ab.",
          en: "Visit all stands, collect stamps and pick up your gift at the end.",
        },
        button: { de: "Karte öffnen", en: "Open card" },
        target: { kind: "stamp" },
        active: false,
        availableFrom: "2026-11-13",
      },
    ],
  },
  stats: {
    visitsByStation: { francis: 24, translation: 19, tts: 17, transcription: 15, interpreter: 12, summary: 9 },
    completeCards: 6,
  },
};

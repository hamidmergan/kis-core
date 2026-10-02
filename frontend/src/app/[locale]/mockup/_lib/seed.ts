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
      "management",
      "info",
      ["Projekt KIS", "Ziele, Antrag und Zeitplan", "Hier hast du gesehen, wofür das Projekt KIS steht und wie es aufgebaut ist."],
      ["Project KIS", "Goals, proposal and schedule", "Here you saw what the KIS project stands for and how it is organised."],
    ),
    station(
      "study",
      "francis",
      ["Studium", "Assistent, Microcredentials und Fachlandkarte", "Hier hast du gesehen, wie das Studium auf internationale Studierende abgestimmt wird."],
      ["Studies", "Assistant, microcredentials and subject map", "Here you saw how the degree programme is adapted for international students."],
    ),
    station(
      "platform",
      "translation",
      ["KIS-Plattform", "KI-Fachsprachen-Trainer und Übersetzung", "Hier hast du gesehen, wie die KIS-Plattform Materialien übersetzt und beim Fachwortschatz hilft."],
      ["KIS platform", "AI technical-language trainer and translation", "Here you saw how the KIS platform translates materials and helps with technical vocabulary."],
    ),
    station(
      "dafl",
      "tts",
      ["Deutsch als Fremdsprache", "Sprachkurse und Buddy-Programm", "Hier hast du gesehen, wie Deutschkurse und Buddys internationale Studierende begleiten."],
      ["German as a foreign language", "Language courses and buddy programme", "Here you saw how German courses and buddies support international students."],
    ),
    station(
      "intercultural",
      "lightbulb",
      ["Interkulturelle Kompetenzen", "Lernfortschritt und Berufseinstieg", "Hier hast du gesehen, wie Lernstand und Berufseinstieg begleitet werden."],
      ["Intercultural skills", "Learning progress and career entry", "Here you saw how learning progress and the move into work are supported."],
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
    visitsByStation: { management: 24, study: 19, platform: 17, dafl: 14, intercultural: 12 },
    completeCards: 6,
  },
};

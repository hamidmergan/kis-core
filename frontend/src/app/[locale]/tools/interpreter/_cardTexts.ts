/** Everything written inside a card follows the language of that card, not the language of the interface. */

import type { LangCode } from "./_types";

export interface CardTexts {
  languages: Record<LangCode, string>;
  languageLabel: string;
  translationLabel: string;
  rename: string;
  renameError: string;
  fieldAria: string;
  translationAria: string;
  empty: string;
  translationHere: string;
  speak: string;
  stop: string;
  idle: string;
  editHint: string;
  translate: string;
  pressTranslate: string;
  listening: string;
  live: string;
  listeningHint: string;
  listeningHintSolo: string;
  noSound: string;
  waiting: (name: string) => string;
  ended: string;
  micDenied: string;
  sttFailed: string;
  nothingHeard: string;
  transcribing: string;
  translating: string;
  failed: string;
  copy: string;
  copied: string;
}

export const CARD_TEXTS: Record<LangCode, CardTexts> = {
  DE: {
    languages: { DE: "Deutsch", "EN-US": "Englisch" },
    languageLabel: "Sprache",
    translationLabel: "Übersetzung",
    rename: "Namen ändern",
    renameError: "Der Name konnte nicht gespeichert werden.",
    fieldAria: "Dein Text",
    translationAria: "Übersetzung",
    empty: "Drück auf Sprechen oder tipp einen Satz.",
    translationHere: "Die Übersetzung erscheint hier.",
    speak: "Sprechen",
    stop: "Fertig",
    idle: "Tippen oder auf Sprechen drücken",
    editHint: "Zum Korrigieren einfach im Feld ändern.",
    translate: "Übersetzen",
    pressTranslate: "Enter drücken oder auf Übersetzen",
    listening: "Hört zu",
    live: "Live-Übersetzung",
    listeningHint: "Auf Fertig drücken, oder die andere Seite drückt Sprechen",
    listeningHintSolo: "Auf Fertig drücken, wenn du fertig bist",
    noSound: "Kein Ton. Sprich lauter oder prüf das Mikrofon.",
    waiting: (name) => `${name} spricht gerade. Sprechen übernimmt das Wort.`,
    ended: "Gespräch beendet.",
    micDenied: "Das Mikrofon ist nicht freigegeben.",
    sttFailed: "Die Spracherkennung ist gerade nicht möglich.",
    nothingHeard: "Nichts verstanden, bitte noch einmal.",
    transcribing: "Erkenne Text",
    translating: "Übersetze",
    failed: "Übersetzung gerade nicht möglich.",
    copy: "Übersetzung kopieren",
    copied: "Kopiert!",
  },
  "EN-US": {
    languages: { DE: "German", "EN-US": "English" },
    languageLabel: "Language",
    translationLabel: "Translation",
    rename: "Change name",
    renameError: "The name could not be saved.",
    fieldAria: "Your text",
    translationAria: "Translation",
    empty: "Press Speak or type a sentence.",
    translationHere: "The translation appears here.",
    speak: "Speak",
    stop: "Done",
    idle: "Type or press Speak",
    editHint: "To correct something, just change it in the field.",
    translate: "Translate",
    pressTranslate: "Press Enter or Translate",
    listening: "Listening",
    live: "Live translation",
    listeningHint: "Press Done, or the other side presses Speak",
    listeningHintSolo: "Press Done when you are finished",
    noSound: "No sound. Speak up or check the microphone.",
    waiting: (name) => `${name} is speaking. Speak takes over.`,
    ended: "Conversation ended.",
    micDenied: "The microphone is not allowed.",
    sttFailed: "Speech recognition is not available right now.",
    nothingHeard: "Nothing understood, please try again.",
    transcribing: "Recognising text",
    translating: "Translating",
    failed: "Translation is not available right now.",
    copy: "Copy translation",
    copied: "Copied!",
  },
};

export const LANG_CODES: LangCode[] = ["DE", "EN-US"];

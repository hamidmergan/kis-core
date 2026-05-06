// Static B1-anchored diagnosis question set. Mirrors the backend list
// (backend/src/features/ai_assistant/routes/language_training/diagnosis.py).
// IDs are stable - never renumber. Backend computes correctness server-side;
// `correct` is intentionally absent here so the answer key never reaches the client.

export type CEFRLevel = "A1" | "A2" | "B1" | "B2" | "C1" | "C2";
export type Skill = "grammar" | "vocabulary" | "reading" | "writing" | "pragmatics";

export interface DiagnosisQuestion {
  id: number;
  type: "single" | "multi" | "free_text";
  skill: Skill;
  prompt: string;
  options?: string[];
}

export interface DiagnosisAnswer {
  questionId: number;
  selectedIndices?: number[];
  text?: string;
}

export interface DiagnosisResult {
  level: CEFRLevel;
  feedback: string;
  skill_scores: Record<Skill, number>;
}

export const DIAGNOSIS_QUESTIONS: DiagnosisQuestion[] = [
  { id: 1, type: "single", skill: "grammar", prompt: "Ich weiß nicht, ___.",
    options: ["wann der Zug kommt", "wann kommt der Zug", "kommt der Zug wann"] },
  { id: 2, type: "multi", skill: "grammar", prompt: "Welche Sätze stehen im Perfekt? (Wähle alle richtigen aus)",
    options: [
      "Er ist gestern nach Berlin gefahren.",
      "Sie liest ein Buch.",
      "Wir haben lange telefoniert.",
      "Ich werde morgen kochen.",
    ] },
  { id: 3, type: "single", skill: "grammar", prompt: "Wir warten ___ den Bus.",
    options: ["auf", "an", "für"] },
  { id: 4, type: "single", skill: "grammar", prompt: "Ich bleibe zu Hause, ___ ich krank bin.",
    options: ["aber", "weil", "trotzdem"] },
  { id: 5, type: "single", skill: "vocabulary", prompt: "Was ist das Gegenteil von „pünktlich“?",
    options: ["sauber", "unpünktlich", "müde"] },
  { id: 6, type: "multi", skill: "grammar", prompt: "Welche Wörter sind Adjektive (Wiewörter)?",
    options: ["Haus", "schnell", "groß", "singen"] },
  { id: 7, type: "single", skill: "vocabulary", prompt: "Welches Wort passt auch für „höflich“?",
    options: ["nett", "laut", "schwierig"] },
  { id: 8, type: "single", skill: "reading",
    prompt: "Text: „Das Meeting wurde von 14 Uhr auf 16 Uhr verschoben.“ Wann findet das Treffen statt?",
    options: ["Früher als geplant", "Später als geplant", "Gar nicht"] },
  { id: 9, type: "single", skill: "pragmatics",
    prompt: "Du bist im Restaurant und möchtest bezahlen. Was sagst du?",
    options: ["Die Rechnung bitte.", "Wo ist der Bahnhof?", "Guten Appetit."] },
  { id: 10, type: "free_text", skill: "writing",
    prompt: "Beschreibe in 2 Sätzen: Was siehst du in deinem Zimmer?" },
  { id: 11, type: "free_text", skill: "writing",
    prompt: "Schreibe eine kurze Entschuldigung an deinen Lehrer, warum du heute nicht kommen kannst." },
  { id: 12, type: "free_text", skill: "writing",
    prompt: "Wie findest du das Wetter heute? Warum?" },
];

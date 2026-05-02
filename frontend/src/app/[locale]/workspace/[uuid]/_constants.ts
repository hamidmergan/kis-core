export const TOOL_LABELS: Record<string, string> = {
  flashcards: "Lernkarten",
  karteikarten: "Karteikarten",
  lueckentext: "Lückentext",
  vokabeltest: "Begriffe-Quiz",
  quiz: "Quiz",
};

// Werte sind CSS-Variablen — Light/Dark-Definitionen liegen in app/globals.css
// (Token-Block "Generisches Badge-Palette-System").
export const TOOL_COLORS: Record<string, { bg: string; color: string }> = {
  flashcards:   { bg: "var(--badge-amber-bg)",   color: "var(--badge-amber-fg)" },
  karteikarten: { bg: "var(--badge-emerald-bg)", color: "var(--badge-emerald-fg)" },
  quiz:         { bg: "var(--badge-yellow-bg)",  color: "var(--badge-yellow-fg)" },
  lueckentext:  { bg: "var(--badge-red-bg)",     color: "var(--badge-red-fg)" },
  vokabeltest:  { bg: "var(--badge-violet-bg)",  color: "var(--badge-violet-fg)" },
};

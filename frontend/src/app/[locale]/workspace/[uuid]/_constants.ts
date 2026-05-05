// CSS custom-property tokens for tool badges (light/dark in app/globals.css).
export const TOOL_COLORS: Record<string, { bg: string; color: string }> = {
  flashcards:   { bg: "var(--badge-amber-bg)",   color: "var(--badge-amber-fg)" },
  karteikarten: { bg: "var(--badge-emerald-bg)", color: "var(--badge-emerald-fg)" },
  quiz:         { bg: "var(--badge-yellow-bg)",  color: "var(--badge-yellow-fg)" },
  lueckentext:  { bg: "var(--badge-red-bg)",     color: "var(--badge-red-fg)" },
  vokabeltest:  { bg: "var(--badge-violet-bg)",  color: "var(--badge-violet-fg)" },
};

export const TOOL_KEYS = [
  "flashcards",
  "karteikarten",
  "lueckentext",
  "vokabeltest",
  "quiz",
] as const;

// Studio form-input limits (frontend-only UX caps; backend stores TEXT without VARCHAR limit).
export const NOTE_TITLE_MAX = 200;
export const NOTE_BODY_MAX = 2000;
export const NOTE_BODY_WARN_AT = 1800;  // shows char counter when draft length crosses this

export const SCHEDULE_TITLE_MAX = 200;
export const SCHEDULE_DESCRIPTION_MAX = 2000;

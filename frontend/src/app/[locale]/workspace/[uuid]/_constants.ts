// CSS custom-property tokens for tool badges (light/dark in app/globals.css).
export const TOOL_COLORS: Record<string, { bg: string; color: string }> = {
  flashcards:   { bg: "var(--badge-amber-bg)",   color: "var(--badge-amber-fg)" },
  karteikarten: { bg: "var(--badge-emerald-bg)", color: "var(--badge-emerald-fg)" },
  quiz:         { bg: "var(--badge-yellow-bg)",  color: "var(--badge-yellow-fg)" },
  grammatik:    { bg: "var(--badge-violet-bg)",  color: "var(--badge-violet-fg)" },
  data_table:   { bg: "var(--badge-orange-bg)",  color: "var(--badge-orange-fg)" },
  mindmap:      { bg: "var(--badge-teal-bg)",    color: "var(--badge-teal-fg)" },
  wortschatz:   { bg: "var(--badge-rose-bg)",    color: "var(--badge-rose-fg)" },
};

// Studio form-input limits (frontend-only UX caps; backend stores TEXT without VARCHAR limit).
export const NOTE_TITLE_MAX = 200;
export const NOTE_BODY_MAX = 2000;
export const NOTE_BODY_WARN_AT = 1800;  // shows char counter when draft length crosses this

export const SCHEDULE_TITLE_MAX = 200;
export const SCHEDULE_DESCRIPTION_MAX = 2000;

// How many saved items one studio tool may hold, a guard against endless clicking rather than a quota.
export const STUDIO_ITEM_MAX = 100;

// A broken formula must never blow up the answer.
export const KATEX_OPTIONS = { throwOnError: false, strict: false as const, errorColor: "var(--muted)" };

export type Side = "left" | "right";
export type LangCode = "DE" | "EN-US";
/** Pending: typed and not sent for translation yet. */
export type TurnStatus = "transcribing" | "pending" | "translating" | "done" | "failed";

/** One thing somebody said or typed, kept in both languages. */
export interface Turn {
  id: string;
  side: Side;
  source: "spoken" | "typed";
  original: string;
  translation: string;
  status: TurnStatus;
  at: number;
  /** A spoken sentence that was corrected by hand. */
  edited: boolean;
}

export interface LanguageOption {
  id: LangCode;
  label: string;
}

export interface ProviderOption {
  id: number;
  label: string;
}

export const otherSide = (side: Side): Side => (side === "left" ? "right" : "left");
export const otherLang = (lang: LangCode): LangCode => (lang === "DE" ? "EN-US" : "DE");
export const localeOf = (lang: LangCode): "de" | "en" => (lang === "DE" ? "de" : "en");
export const newId = () => `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 7)}`;

// Flag emoji per language code, used to label TTS voices. The empty key is the
// universal (no-language) voice.
export const LANGUAGE_FLAG: Record<string, string> = {
  "": "🌐", // universal voice (no language set)
  de: "🇩🇪", en: "🇺🇸", fr: "🇫🇷", es: "🇪🇸",
  it: "🇮🇹", nl: "🇳🇱", pt: "🇵🇹", pl: "🇵🇱",
  tr: "🇹🇷", zh: "🇨🇳", ja: "🇯🇵", ko: "🇰🇷",
};

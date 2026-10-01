import { FontCharset } from "@embedpdf/models";
import type { FontFallbackConfig } from "@embedpdf/engines";
import { fonts as scFonts } from "@embedpdf/fonts-sc";
import { fonts as arabicFonts } from "@embedpdf/fonts-arabic";
import { fonts as hebrewFonts } from "@embedpdf/fonts-hebrew";
import { fonts as latinFonts } from "@embedpdf/fonts-latin";

// Scoped to our actual population (exchange students, refugees): simplified Chinese,
// Arabic/Hebrew, and Latin/Cyrillic (covers Russian, Ukrainian, German, English).
// Deliberately skips Japanese/Korean/traditional Chinese to avoid ~100MB of unused fonts
// in the bundle; a PDF needing one of those shows placeholder glyphs instead.

type FontFile = { file: string; weight?: number; italic?: boolean };

// Mirrors @embedpdf/engines' own toFontVariants/buildCdnFontConfig, but against
// our self-hosted copies under public/fonts/ instead of jsDelivr.
function toFontVariants(files: FontFile[], baseUrl: string) {
  return files.map((f) => ({ url: `${baseUrl}/${f.file}`, weight: f.weight, italic: f.italic }));
}

// Must be absolute: the PDF engine runs in a worker loaded from a blob: URL,
// where a relative path doesn't resolve against our origin.
export function buildSelfHostedFontFallback(origin: string): FontFallbackConfig {
  const base = (lang: string) => `${origin}/fonts/${lang}`;
  return {
    fonts: {
      [FontCharset.GB2312]: toFontVariants(scFonts, base("sc")),
      [FontCharset.ARABIC]: toFontVariants(arabicFonts, base("arabic")),
      [FontCharset.HEBREW]: toFontVariants(hebrewFonts, base("hebrew")),
      [FontCharset.CYRILLIC]: toFontVariants(latinFonts, base("latin")),
      [FontCharset.GREEK]: toFontVariants(latinFonts, base("latin")),
      [FontCharset.VIETNAMESE]: toFontVariants(latinFonts, base("latin")),
    },
  };
}

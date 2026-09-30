import { MAX_IMAGE_BYTES } from "@/lib/constants";

export const FORMATE = ["1:1", "16:9", "4:3", "3:4", "9:16"] as const;
export const GROESSEN = ["klein", "mittel", "gross"] as const;
export const QUALITAETEN = ["entwurf", "standard", "hoch"] as const;
export const STILE = ["keiner", "foto", "illustration", "skizze", "aquarell", "3d", "flach", "thl"] as const;
export const AUFGABEN = ["beschreiben", "text", "frage"] as const;
export const SCHNELLAKTIONEN = ["weiss", "skizze", "ohneText", "kraeftig", "thl"] as const;
export const ALLOWED_EXTS = new Set([".png", ".jpg", ".jpeg"]);

export type Format = (typeof FORMATE)[number];
export type Groesse = (typeof GROESSEN)[number];

// The same table as backend/src/features/bild/optionen.py, only shown here, the backend decides.
const PIXEL: Record<Format, readonly [string, string, string]> = {
  "1:1": ["768x768", "1024x1024", "1440x1440"],
  "16:9": ["1024x576", "1344x768", "1920x1088"],
  "4:3": ["896x672", "1152x864", "1664x1248"],
  "3:4": ["672x896", "864x1152", "1248x1664"],
  "9:16": ["576x1024", "768x1344", "1088x1920"],
};

/** The pixels of a format and size as the person reads them, "1344 × 768". */
export function pixelLabel(format: Format, groesse: Groesse): string {
  return pixelText(PIXEL[format][GROESSEN.indexOf(groesse)]);
}

/** A stored size like "1344x768" as the person reads it. */
export function pixelText(groesse: string): string {
  return groesse.replace("x", " × ");
}

type CommonT = (key: string, params?: Record<string, string | number | Date>) => string;

export function validateImageFile(file: File, t: CommonT): string | null {
  const ext = "." + file.name.split(".").pop()?.toLowerCase();
  if (!ALLOWED_EXTS.has(ext)) return t("onlyExtsAllowed", { exts: "PNG, JPG" });
  if (file.size > MAX_IMAGE_BYTES) return t("fileTooLarge", { n: 20 });
  return null;
}

/** A PNG turned into a JPG in the browser, a smaller file for slides and mail. */
export async function alsJpg(blob: Blob): Promise<Blob> {
  const bild = await createImageBitmap(blob);
  const leinwand = document.createElement("canvas");
  leinwand.width = bild.width;
  leinwand.height = bild.height;
  const ctx = leinwand.getContext("2d");
  if (!ctx) throw new Error("canvas");
  // JPG has no transparency, a white ground keeps transparent parts from turning black.
  ctx.fillStyle = "#fff";
  ctx.fillRect(0, 0, leinwand.width, leinwand.height);
  ctx.drawImage(bild, 0, 0);
  return new Promise((resolve, reject) =>
    leinwand.toBlob((b) => (b ? resolve(b) : reject(new Error("jpg"))), "image/jpeg", 0.9),
  );
}

/** Saves a blob under a name, the browser's own download. */
export function speichern(blob: Blob, name: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/** Copies text, over plain http the browser has no clipboard interface, a hidden field does the job there. */
export async function kopieren(text: string): Promise<void> {
  if (navigator.clipboard && window.isSecureContext) {
    await navigator.clipboard.writeText(text);
    return;
  }
  const feld = document.createElement("textarea");
  feld.value = text;
  feld.style.position = "fixed";
  feld.style.opacity = "0";
  document.body.appendChild(feld);
  feld.select();
  document.execCommand("copy");
  feld.remove();
}

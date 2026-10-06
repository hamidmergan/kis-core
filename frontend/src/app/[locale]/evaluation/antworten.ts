import { istSichtbar } from "./sichtbarkeit";

type ShowIf = { question_id: string; in: string[] };
type Frage = { id: string; type: "choice" | "multi" | "text"; text: string; show_if?: ShowIf };
type Wert = string | string[];

/** The answers worth sending: visible questions only, in the evaluation's own order, skipped ones left out. */
export function zuSenden(
  fragen: Frage[],
  antworten: Record<string, Wert>,
): { question_id: string; value: Wert }[] {
  return fragen
    .filter((f) => istSichtbar(f, antworten))
    .filter((f) => {
      const wert = antworten[f.id];
      if (wert === undefined) return false;
      if (Array.isArray(wert)) return wert.length > 0;
      return typeof wert === "string" ? wert.trim() !== "" : true;
    })
    .map((f) => ({ question_id: f.id, value: antworten[f.id] }));
}

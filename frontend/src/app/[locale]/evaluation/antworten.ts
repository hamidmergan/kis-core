type Frage = { id: string; type: "scale" | "text"; text: string };

/** The answers worth sending, in the evaluation's own order, skipped questions left out. */
export function zuSenden(
  fragen: Frage[],
  antworten: Record<string, string | number>,
): { question_id: string; value: string | number }[] {
  return fragen
    .filter((f) => {
      const wert = antworten[f.id];
      if (wert === undefined) return false;
      return typeof wert === "string" ? wert.trim() !== "" : true;
    })
    .map((f) => ({ question_id: f.id, value: antworten[f.id] }));
}

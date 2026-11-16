import type { ExerciseItem, ExerciseItemSource } from "../../_types";
import { _sourceChipKey } from "../../_utils";

type WithSources = Pick<ExerciseItem, "sources" | "source_label" | "page_number" | "start_time">;

/** The places an exercise cites, each one once, with the single old-style source as fallback. */
export function itemSources(card: WithSources): ExerciseItemSource[] {
  const cardSource = card.source_label
    ? { source_label: card.source_label, page_number: card.page_number, start_time: card.start_time }
    : null;
  const raw: ExerciseItemSource[] = card.sources?.length ? card.sources : cardSource ? [cardSource] : [];
  const seen = new Set<string>();
  return raw.filter((s) => {
    const k = _sourceChipKey(s.source_label, s.page_number, s.start_time, s.highlight_text);
    if (seen.has(k)) return false;
    seen.add(k);
    return true;
  });
}

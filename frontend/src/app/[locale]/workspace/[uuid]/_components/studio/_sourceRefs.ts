import type { Source } from "../../_types";
import { _isMediaFile } from "../../_utils";
import { chipTargetKey } from "../chat/_citations";

export interface MindmapNodeData {
  topic: string;
  children?: MindmapNodeData[];
  source_label?: string;
  page_number?: number | string;
  keyword?: string;
}

/** Turns a timestamp label "M:SS" or "H:MM:SS" into seconds, anything else is no time. */
export function timeLabelSeconds(label: string): number | undefined {
  const parts = label.split(":").map(Number);
  if (parts.length === 3) return parts[0] * 3600 + parts[1] * 60 + parts[2];
  if (parts.length === 2) return parts[0] * 60 + parts[1];
  return undefined;
}

/** The page a studio result cites, 0 when it names none. */
export function pageNumberOf(page: number | string | null | undefined): number {
  return typeof page === "number" ? page : parseInt(String(page), 10) || 0;
}

/** A source label rarely matches a filename exactly, so fall back to a loose match. */
export function findSource(sources: Source[], label: string): Source | undefined {
  const lower = label.toLowerCase();
  return sources.find((s) => s.filename === label)
    ?? sources.find((s) => s.filename.toLowerCase() === lower)
    ?? sources.find((s) => lower.includes(s.filename.toLowerCase()) || s.filename.toLowerCase().includes(lower));
}

/** The chip key has to match the one the chat chips use, both mark the same target. */
export function chipKey(src: Source, pageNumber: number | string | undefined): string {
  if (_isMediaFile(src.filename) && typeof pageNumber === "string") {
    return chipTargetKey(src.uuid, 0, timeLabelSeconds(pageNumber) ?? 0);
  }
  return chipTargetKey(src.uuid, pageNumberOf(pageNumber), undefined);
}

/** Numbers the sources the way the user ticked them and collects the ones the map really cites. */
export function numberMindmapSources(
  mindmap: MindmapNodeData | null,
  pickedSources: { number: number; filename: string }[] | undefined,
): { index: Map<string, number>; used: Set<string> } {
  const index = new Map<string, number>();
  const used = new Set<string>();
  for (const s of pickedSources || []) {
    if (!index.has(s.filename)) index.set(s.filename, s.number);
  }
  function collect(node: MindmapNodeData) {
    if (node.source_label) {
      used.add(node.source_label);
      // Older maps carry no picked list, then the tree order numbers them.
      if (!index.has(node.source_label)) index.set(node.source_label, index.size + 1);
    }
    node.children?.forEach(collect);
  }
  if (mindmap) collect(mindmap);
  return { index, used };
}

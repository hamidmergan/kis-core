import type { PanelKey } from "../_types";

type Layout = Record<PanelKey, boolean>;

const ALL_OPEN: Layout = { quellen: true, chat: true, studio: true };

function isAlone(layout: Layout, key: PanelKey, visible: PanelKey[]): boolean {
  return visible.every((k) => layout[k] === (k === key));
}

// Double-clicking a header shows that panel alone, the next one restores the layout from before.
export function nextFocusLayout(
  current: Layout,
  key: PanelKey,
  saved: Layout | null,
  visible: PanelKey[],
): { panels: Layout; saved: Layout | null } {
  if (isAlone(current, key, visible)) {
    const back = saved && !isAlone(saved, key, visible) ? saved : ALL_OPEN;
    return { panels: back, saved: null };
  }
  const panels = { ...current };
  for (const k of visible) panels[k] = k === key;
  return { panels, saved: current };
}

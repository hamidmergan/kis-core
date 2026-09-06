/**
 * The seven steps of the guided tour through a course.
 *
 * Rule for what belongs in here: only what nobody finds on their own. An
 * upload button next to a file list explains itself, the selection bar in a
 * PDF does not. Whoever adds a step should be able to say why someone would
 * miss the thing otherwise.
 *
 * `anchor` is the contract with the components: they carry `data-tour="..."`.
 * Never select on CSS classes, those move with every restyle. When an anchor
 * is missing the step is skipped instead of pointing into the void, see
 * useTour.
 */
export interface TourStep {
  /** Value of the data-tour attribute the step points at. */
  anchor: string;
  /** Key below workspace.detail.tour.steps in the message files. */
  key: string;
  /** Step waits for the person to do something, not just to read. */
  interactive?: boolean;
  /** Placement hint for the popover, driver.js decides the rest. */
  side?: "top" | "right" | "bottom" | "left";
  /**
   * Anchor only exists once an earlier step opened it. Such a step is kept as
   * long as its precondition holds, otherwise the most valuable step of the
   * tour would quietly drop out because no PDF happens to be open yet.
   */
  opensOnDemand?: boolean;
}

export const TOUR_STEPS: TourStep[] = [
  { anchor: "preview-entry", key: "preview", side: "bottom" },
  { anchor: "sources-panel", key: "sources", side: "right" },
  { anchor: "source-row", key: "openSource", interactive: true, side: "right" },
  { anchor: "pdf-viewer", key: "selectionBar", interactive: true, side: "left", opensOnDemand: true },
  { anchor: "chat-input", key: "chat", interactive: true, side: "top" },
  { anchor: "chat-panel", key: "chips", side: "left" },
  { anchor: "studio-panel", key: "studio", side: "left" },
];

import { TOOL_ROUTES, type ToolKey } from "@/lib/modules";

export interface RundgangSchritt {
  /** Key below toolsTour in the message files. */
  key: string;
  /** Value of the data-tour attribute the station points at. */
  anker: string;
  /** Tool page the station opens first, empty for stations that run anywhere. */
  route?: string;
  side?: "top" | "right" | "bottom" | "left";
  /** No real target, the closing station shows centered instead of pointing anywhere. */
  ohneZiel?: boolean;
}

/** Anchor of a tool page's working area, one per tool so a jump never lands on the page just leaving. */
const werkzeugAnker = (key: ToolKey) => `tool-${key}`;

/**
 * The tour through the tools, one station per tool.
 *
 * Only what nobody finds on their own belongs in here: the name in the sidebar
 * says what a tool is called, not what it takes or where the result lands. The
 * tour therefore opens each tool itself and closes at the jobs entry.
 *
 * Tools somebody may not use are dropped instead of pointing into the void,
 * and the order follows the sidebar so the tour never jumps up and down its
 * list. Without a single tool there is no sidebar either, so there is nothing
 * left to show.
 */
export function werkzeugRundgang(sichtbar: readonly ToolKey[]): RundgangSchritt[] {
  const werkzeuge = TOOL_ROUTES.filter((t) => sichtbar.includes(t.key));
  if (werkzeuge.length === 0) return [];
  return [
    { key: "seitenleiste", anker: "tools-sidebar", side: "right" },
    // Below the working area: the target is as wide as the page, beside it the
    // popover covered the very sidebar the tour just came from.
    ...werkzeuge.map((t) => ({
      key: t.key,
      anker: werkzeugAnker(t.key),
      route: t.href,
      side: "bottom" as const,
    })),
    { key: "auftraege", anker: "jobs-entry", side: "bottom" },
    { key: "abschluss", anker: "abschluss", ohneZiel: true },
  ];
}

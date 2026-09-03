/**
 * The guided tour through the demo course, station by station.
 *
 * Unlike the short tour in steps.ts this one knows its course: it names the
 * files of the demo module and opens them itself, so nobody has to click
 * along. That is also its limit, in another course the anchors would be wrong,
 * which is why useTour only drives this script in the demo module.
 *
 * The tour opens and switches, it never sends anything. A glossary entry and a
 * note are put in place beforehand (see the backend, demo/tour-content), the
 * tour only shows them.
 */

export type StudioReiter = "tools" | "glossary" | "notes" | "statistik" | "schedule";

export interface TourAktionen {
  /** Ticks this material and unticks every other one. */
  nurWaehlen: (dateiPraefix: string) => void;
  /** Opens the material in the viewer. */
  oeffnen: (dateiPraefix: string) => void;
  /** Brings the studio forward and switches its tab. */
  studioReiter: (reiter: StudioReiter) => void;
  /** Brings the material list forward, on narrow screens the viewer covers it. */
  materialListe: () => void;
  /** Fetches glossary and notes again, the examples arrive after the page did. */
  beispieleLaden: () => void;
  /** Brings the chat forward and puts the example question and answer in it. */
  chatBeispielZeigen: () => void;
}

export interface DemoSchritt {
  /** Key below workspace.detail.tour.demo in the message files. */
  key: string;
  /** Element the step points at, without one the window stands in the middle. */
  ziel?: () => Element | null;
  side?: "top" | "right" | "bottom" | "left";
  /** Runs before the step, opens whatever it points at. */
  vorbereiten?: (a: TourAktionen) => void;
  /** Milliseconds the preparation needs before the step is shown. */
  wartezeit?: number;
  /**
   * What the step looks like for whoever may not create modules themselves.
   * `null` drops the step, an object overrides the named fields.
   */
  studi?: Partial<DemoSchritt> | null;
}

/** The two materials the tour works with, named by the start of their file name.
 * The PDF sits at the very top of the list (newest upload first), so the tour
 * never has to scroll to reach it. */
export const DEMO_PDF = "DEMO_Folien_06";
export const DEMO_VIDEO = "DEMO_Vorlesung_01";

const anker = (name: string) => (): Element | null =>
  document.querySelector(`[data-tour="${name}"]`);

/** The row of a material, found by its file name and not by its position. */
function zeile(praefix: string): HTMLElement | null {
  const zeilen = Array.from(document.querySelectorAll<HTMLElement>('[data-tour="source-row"]'));
  return zeilen.find((z) => (z.textContent ?? "").includes(praefix)) ?? null;
}

function zeilenHaken(praefix: string): Element | null {
  return zeile(praefix)?.querySelector('[data-tour="source-check"]') ?? null;
}

export const DEMO_SCHRITTE: DemoSchritt[] = [
  { key: "willkommen", studi: { key: "willkommenStudi" } },
  {
    key: "materialien",
    ziel: anker("sources-panel"),
    side: "right",
    vorbereiten: (a) => a.materialListe(),
    studi: { key: "materialienStudi" },
  },
  // Both buttons belong to the owner side, which students never get to see.
  { key: "hochladen", ziel: anker("add-source"), side: "bottom", studi: null },
  {
    key: "hinweis",
    ziel: anker("add-staff-note"),
    side: "bottom",
    // Students cannot pin anything, but they read what was pinned for them.
    studi: { key: "hinweisStudi", ziel: anker("staff-note"), side: "right" },
  },
  {
    key: "auswahl",
    ziel: () => zeilenHaken(DEMO_PDF),
    side: "right",
    vorbereiten: (a) => a.nurWaehlen(DEMO_PDF),
  },
  { key: "quelleOeffnen", ziel: () => zeile(DEMO_PDF), side: "right" },
  {
    key: "auswahlleiste",
    ziel: anker("pdf-viewer"),
    side: "right",
    vorbereiten: (a) => a.oeffnen(DEMO_PDF),
    wartezeit: 1200,
  },
  {
    key: "glossar",
    ziel: anker("studio-panel"),
    side: "left",
    vorbereiten: (a) => a.studioReiter("glossary"),
    wartezeit: 900,
  },
  {
    key: "video",
    ziel: anker("transcript-panel"),
    side: "right",
    vorbereiten: (a) => a.oeffnen(DEMO_VIDEO),
    wartezeit: 1600,
  },
  { key: "transkriptNotiz", ziel: anker("transcript-note"), side: "right" },
  {
    key: "notizen",
    ziel: anker("studio-panel"),
    side: "left",
    vorbereiten: (a) => a.studioReiter("notes"),
    wartezeit: 900,
  },
  {
    key: "chat",
    ziel: anker("chat-panel"),
    side: "left",
    vorbereiten: (a) => a.chatBeispielZeigen(),
    wartezeit: 900,
  },
  {
    key: "werkzeuge",
    ziel: anker("tools-grid"),
    side: "left",
    vorbereiten: (a) => a.studioReiter("tools"),
    wartezeit: 900,
  },
  {
    key: "statistik",
    ziel: anker("studio-panel"),
    side: "left",
    vorbereiten: (a) => a.studioReiter("statistik"),
    wartezeit: 900,
  },
  {
    key: "zeitplan",
    ziel: anker("studio-panel"),
    side: "left",
    vorbereiten: (a) => a.studioReiter("schedule"),
    wartezeit: 900,
  },
  { key: "schluss", studi: { key: "schlussStudi" } },
];

/**
 * The script for one person, cut to what they may actually do.
 *
 * Whoever may not create modules loses the stations about the owner controls
 * and reads a different wording where the full script speaks to teachers. The
 * cut happens here and not in the tour itself, so the running order and the
 * step count stay in one place.
 */
export function demoSchritte(darfModuleAnlegen: boolean): DemoSchritt[] {
  if (darfModuleAnlegen) return DEMO_SCHRITTE.map(({ studi: _studi, ...rest }) => rest);
  return DEMO_SCHRITTE.flatMap(({ studi, ...rest }) =>
    studi === null ? [] : [{ ...rest, ...studi }],
  );
}

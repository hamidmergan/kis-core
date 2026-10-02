import type { ToolKey } from "@/lib/modules";

export type Lang = "de" | "en";
export type Text2 = Record<Lang, string>;
export type IconKey = ToolKey | "francis" | "info" | "gift" | "star" | "lightbulb" | "qrCode";

export interface Station {
  id: string;
  icon: IconKey;
  name: Text2;
  blurb: Text2;
  francis: Text2;
}

export type TileTarget =
  | { kind: "stamp" }
  | { kind: "info" }
  | { kind: "internal"; path: string }
  | { kind: "directLogin"; accessCode: string };

export interface EventTile {
  id: string;
  icon: IconKey;
  title: Text2;
  body: Text2;
  button: Text2;
  target: TileTarget;
  /** The button only works while this is on, the admin switches it. */
  active: boolean;
  /** Shown as a note while the button is locked, YYYY-MM-DD, empty for no date. */
  availableFrom: string;
}

export interface EventBlock {
  enabled: boolean;
  ignoreWindow: boolean;
  from: string;
  until: string;
  heading: Text2;
  text: Text2;
  tiles: EventTile[];
}

/** Owned by the admin, becomes backend settings once the mockup is accepted. */
export interface MockupConfig {
  stations: Station[];
  masterCode: string;
  eventBlock: EventBlock;
  stats: { visitsByStation: Record<string, number>; completeCards: number };
}

/** Owned by one visitor's phone, becomes a per-account record later. */
export interface MockupCard {
  stamped: Record<string, number>;
  failedAttempts: number;
  lockUntil: number | null;
  linkedToAccount: boolean;
  completedAt: number | null;
}

export const EMPTY_CARD: MockupCard = {
  stamped: {},
  failedAttempts: 0,
  lockUntil: null,
  linkedToAccount: false,
  completedAt: null,
};

export const MAX_TILES = 4;

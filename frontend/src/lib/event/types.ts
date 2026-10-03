import type { ToolKey } from "@/lib/modules";

export type Lang = "de" | "en";
export type Text2 = Record<Lang, string>;
export type IconKey = ToolKey | "francis" | "info" | "gift" | "star" | "lightbulb" | "qrCode" | "platform";

export interface Station {
  id: string;
  /** Four characters printed on this stand's poster, a hit stamps this stand only. */
  code: string;
  icon: IconKey;
  name: Text2;
  blurb: Text2;
  francis: Text2;
}

/** A stand without its code, what visitors see. */
export type PublicStation = Omit<Station, "code">;

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

/** What the admin edits and the server stores, the codes only travel to the admin. */
export interface EventConfig {
  stations: Station[];
  eventBlock: EventBlock;
  /** Leaves the code off every poster so a visitor has to scan, the admin still sees it. */
  hideCodeOnPosters: boolean;
}

/** What every visitor may read, no codes, the block is null while it is off or outside its period. */
export interface PublicEvent {
  stations: PublicStation[];
  eventBlock: EventBlock | null;
}

/** One visitor's card as the server keeps it, times are epoch milliseconds. */
export interface Card {
  stamped: Record<string, number>;
  completedAt: number | null;
  lockedUntil: number | null;
  attemptsLeft: number;
}

export interface EventStats {
  visitsByStation: Record<string, number>;
  completeCards: number;
}

export const EMPTY_CARD: Card = { stamped: {}, completedAt: null, lockedUntil: null, attemptsLeft: 5 };

export const MAX_TILES = 4;

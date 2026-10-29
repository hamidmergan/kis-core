import type { ErgebnisAngaben } from "@/components/jobs/ErgebnisInfo";

/** The page as the backend stores it in page.json, plain text only. */

export type CardIcon = "none" | "info" | "check" | "x" | "warning" | "idea";

/** A title with its explanation, the item of steps, cycles, levels and accordions. */
export interface Entry {
  title: string;
  text: string;
}

/** One side of a comparison or one circle of an overlap. */
export interface Side {
  title: string;
  items: string[];
}

export type Block =
  | { kind: "text"; text: string }
  | { kind: "bullets"; items: string[] }
  /** Older pages only, it is drawn as a formula or a term and never written any more. */
  | { kind: "highlight"; key: string; text: string }
  | { kind: "cards"; cards: { icon: CardIcon; title: string; text: string }[]; cols?: 1 }
  | { kind: "steps"; steps: Entry[] }
  | { kind: "figures"; figures: { value: string; label: string }[] }
  | { kind: "bars"; bars: { label: string; value: number; text: string }[]; max?: number }
  | { kind: "table"; caption: string; header: string[]; rows: string[][] }
  /** keyword is one word of the sentence the look may underline. */
  | { kind: "quote"; text: string; keyword?: string }
  | { kind: "checklist"; items: string[] }
  | { kind: "definitions"; items: { term: string; text: string }[] }
  | { kind: "accordion"; items: Entry[] }
  | { kind: "cycle"; center: string; steps: Entry[] }
  | { kind: "timeline"; events: { date: string; title: string; text: string }[] }
  | { kind: "tree"; root: string; branches: { title: string; leaves: string[] }[] }
  | { kind: "levels"; caption: string; items: Entry[] }
  | { kind: "scale"; caption: string; left: string; right: string; items: { label: string; pos: number }[] }
  /** "good_bad" sets what helps against what harms, "neutral" two things side by side. */
  | { kind: "versus"; tone: "neutral" | "good_bad"; a: Side; b: Side }
  | {
      kind: "matrix";
      x: string;
      y: string;
      /** tl, tr, bl, br: the quadrant, top means high on y, right high on x. */
      cells: { pos: "tl" | "tr" | "bl" | "br"; title: string; text: string }[];
      /** Positions from 0 to 1 on both axes, may be empty. */
      points: { label: string; x: number; y: number }[];
    }
  | { kind: "venn"; a: Side; b: Side; both: string[]; c?: Side }
  | { kind: "formula"; key: string; text: string; parts: { sym: string; text: string }[]; example: string[] }
  | { kind: "mistakes"; pairs: { wrong: string; right: string }[] }
  | { kind: "example"; title: string; situation: string; steps: string[]; result: string }
  | {
      kind: "chart";
      /** pie shows the shares of one whole and draws one series. */
      chart_type: "line" | "bar" | "pie";
      caption: string;
      x_label: string;
      y_label: string;
      categories: string[];
      series: { name: string; values: number[] }[];
    }
  | { kind: "image"; src: string; alt: string; prompt: string; caption: string }
  | {
      kind: "mindmap";
      center: string;
      caption: string;
      branches: { title: string; to: string; leaves: string[] }[];
    }
  | { kind: "wordcloud"; caption: string; words: [string, number][] }
  /** A field of an added section the owner has not filled yet, readers never see it. */
  | { kind: "empty" };

export type BlockKind = Block["kind"];

/** The grids an added section can take, each key with its number of fields. */
export const LAYOUTS = { "1": 1, "2": 2, "21": 2, "12": 2, "3": 3, "4": 4, "1-2": 3 } as const;
export type Layout = keyof typeof LAYOUTS;

/** Where an added section shows its title and lead, "none" shows neither. */
export const HEADINGS = ["top", "left", "right", "bottom", "none"] as const;
export type Heading = (typeof HEADINGS)[number];

export interface Section {
  id: string;
  title: string;
  lead: string;
  blocks: Block[];
  hero?: boolean;
  meta?: string;
  hidden?: boolean;
  /** Set on a section the owner added, its blocks are the fields of this grid. */
  layout?: Layout;
  heading?: Heading;
}

/** The look of a page, the run picks it from the material. */
export type Design = "chapters" | "timeline" | "magazine" | "guide";

export interface Page {
  version: number;
  lang: string;
  design?: Design;
  sections: Section[];
  footer: string;
  saved_at?: string;
}

export interface Limits {
  sections: number;
  blocks: number;
  images: number;
  tableRows: number;
  tableCols: number;
  items: number;
  short: number;
  item: number;
  long: number;
  imagePrompt: number;
  series: number;
  branches: number;
  leaves: number;
  words: number;
  /** A chart category, a mind map node or word. */
  label: number;
  mapLabel: number;
}

/** A language a reader can switch to, its label in its own language. */
export interface LanguageChoice {
  key: string;
  label: string;
}

/** What the owner sees in the language window. */
export interface Languages {
  own: LanguageChoice;
  languages: (LanguageChoice & { state: "running" | "done" | "failed"; stale: boolean })[];
  choices: LanguageChoice[];
  max: number;
}

export interface PageCard {
  job_uuid: string;
  status: string;
  progress: { step?: string; part?: number; total?: number };
  error: string | null;
  title: string;
  image: string;
  sources: string;
  created_at: string | null;
  updated_at: string | null;
  shared: boolean;
  /** The link opens without an askFrancis account. */
  public: boolean;
  code: string | null;
  /** What the page was made with, for the owner's info icon. */
  info: ErgebnisAngaben;
}

export interface PagesList {
  pages: PageCard[];
  /** shared: others may open the overview, the pages link back to it. */
  collection: { code: string; count: number; shared: boolean };
  max: number;
  maxSources: number;
  /** The default look of the pictures, the form starts with it. */
  imageStyle: string;
  imageStyleMax: number;
  /** The styles of the image tool with their sentences, a choice fills the field. */
  imageStyles: Record<string, string>;
  extensions: string[];
}

export interface OwnPage {
  job_uuid: string;
  page: Page;
  edited: boolean;
  limits: Limits;
  shared: boolean;
  /** The link opens without an askFrancis account. */
  public: boolean;
  code: string | null;
  collection: string;
}

export interface SharedPage {
  page: Page;
  owner: { name: string; code: string | null };
  limits: Limits;
  languages: LanguageChoice[];
  language: string;
}

export interface Collection {
  owner: { name: string };
  own: boolean;
  /** Others may open the overview, without it only its owner sees it. */
  shared: boolean;
  pages: { code: string; title: string; image: string; updated_at: string | null }[];
}

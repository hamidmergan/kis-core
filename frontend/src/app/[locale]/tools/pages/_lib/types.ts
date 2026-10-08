import type { ErgebnisAngaben } from "@/components/jobs/ErgebnisInfo";

/** The page as the backend stores it in page.json, plain text only. */

export type CardIcon = "none" | "info" | "check" | "x" | "warning" | "idea";

export type Block =
  | { kind: "text"; text: string }
  | { kind: "bullets"; items: string[] }
  | { kind: "highlight"; key: string; text: string }
  | { kind: "cards"; cards: { icon: CardIcon; title: string; text: string }[]; cols?: 1 }
  | { kind: "steps"; steps: { title: string; text: string }[] }
  | { kind: "figures"; figures: { value: string; label: string }[] }
  | { kind: "bars"; bars: { label: string; value: number; text: string }[]; max?: number }
  | { kind: "table"; caption: string; header: string[]; rows: string[][] }
  | {
      kind: "chart";
      chart_type: "line" | "bar";
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
  code: string | null;
  /** What the page was made with, for the owner's info icon. */
  info: ErgebnisAngaben;
}

export interface PagesList {
  pages: PageCard[];
  collection: { code: string; count: number };
  max: number;
  maxSources: number;
  /** The default look of the pictures, the form starts with it. */
  imageStyle: string;
  imageStyleMax: number;
  extensions: string[];
}

export interface OwnPage {
  job_uuid: string;
  page: Page;
  edited: boolean;
  limits: Limits;
  shared: boolean;
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
  pages: { code: string; title: string; image: string; updated_at: string | null }[];
}

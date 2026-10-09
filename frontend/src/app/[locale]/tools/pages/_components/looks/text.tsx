"use client";

import { useContext, useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { Check, Lightbulb, Warning, X } from "@phosphor-icons/react";
import type { Block, BlockKind, CardIcon, Limits } from "../../_lib/types";
import type { Look, LookProps, Looks } from "./registry";
import { Grow } from "./shared";
import { EditCtx, Txt } from "../Txt";
import "./text.css";

type B<K extends BlockKind> = Extract<Block, { kind: K }>;

/** Every look sits in a container, so its narrow rules can use container queries. */
function Root({ cls, children }: { cls?: string; children: React.ReactNode }) {
  return <div className="v-tx-q">{cls ? <div className={cls}>{children}</div> : children}</div>;
}

const PATHS = {
  check: "M5 12.5l4.5 4.5L19 7.5",
  right: "M4 12h15M13 6l6 6-6 6",
};
function Ic({ n }: { n: keyof typeof PATHS }) {
  return <svg className="v-tx-ic" viewBox="0 0 24 24" aria-hidden="true"><path d={PATHS[n]} /></svg>;
}
// A filled double quotation mark, drawn so it does not depend on the font.
const QUOTE = (
  <svg className="v-qt-mark" viewBox="0 0 40 30" aria-hidden="true">
    <path d="M3 3h13v13c0 6-4 10-10 10H3v-5h3c3 0 5-2 5-5H3z" />
    <path d="M24 3h13v13c0 6-4 10-10 10h-3v-5h3c3 0 5-2 5-5h-8z" />
  </svg>
);

/** The add button under a list, the editor grows the list at p. */
function AddItem({ p, n, limits }: { p: string; n: number; limits: Limits }) {
  const t = useTranslations("tools.pages");
  return <Grow items={[{ what: "item", path: p, full: n >= limits.items, label: t("addItem"), limit: t("maxItems", { max: limits.items }) }]} />;
}

const two = (i: number) => String(i + 1).padStart(2, "0");

/* ---------- Fließtext ---------- */

function textLook(name: string, cls: string, fits?: (b: B<"text">) => boolean, textCls?: string): Look<"text"> {
  return {
    name, fits,
    View: function TextLook({ b, p, limits }) {
      return <Root cls={cls}><Txt path={`${p}.text`} value={b.text} as="p" className={textCls} max={limits.long} /></Root>;
    },
  };
}

const TEXT: Look<"text">[] = [
  textLook("Schlicht", "v-tx-plain"),
  textLook("Zwei Spalten", "v-tx-cols", (b) => b.text.length >= 400),
  textLook("Initial", "v-tx-init", (b) => b.text.length >= 200),
  textLook("Erste Zeile groß", "v-tx-leadin", (b) => b.text.length >= 200),
  textLook("Akzentlinie", "v-tx-rule", undefined, "v-tx-first"),
];

/* ---------- Liste ---------- */

function listLook(name: string, cls: string, opts: { fits?: (b: B<"bullets">) => boolean; lead?: (i: number) => React.ReactNode; ol?: boolean } = {}): Look<"bullets"> {
  return {
    name, fits: opts.fits,
    View: function ListLook({ b, p, limits }) {
      const Tag = opts.ol ? "ol" : "ul";
      return (
        <Root>
          <Tag className={cls}>
            {b.items.map((v, i) => (
              <li key={i} data-d={`${p}.items.${i}`}>
                {opts.lead?.(i)}
                <Txt path={`${p}.items.${i}`} value={v} as="span" className="v-bl-t" max={limits.item} />
              </li>
            ))}
          </Tag>
          <AddItem p={p} n={b.items.length} limits={limits} />
        </Root>
      );
    },
  };
}

const BULLETS: Look<"bullets">[] = [
  listLook("Punkte", "v-bl-dots"),
  listLook("Linien", "v-bl-lines"),
  listLook("Zwei Spalten", "v-bl-two", { fits: (b) => b.items.length >= 4 }),
  listLook("Große Ziffern", "v-bl-num", { ol: true, lead: (i) => <span className="v-bl-n" aria-hidden="true">{i + 1}</span> }),
  {
    name: "Etiketten",
    fits: (b) => b.items.every((v) => v.length <= 24),
    View: function Tags({ b, p, limits }) {
      return (
        <Root>
          <div className="v-bl-tags">
            {b.items.map((v, i) => (
              <span className="v-bl-tag" key={i} data-d={`${p}.items.${i}`}>
                <Txt path={`${p}.items.${i}`} value={v} as="span" max={limits.item} />
              </span>
            ))}
          </div>
          <AddItem p={p} n={b.items.length} limits={limits} />
        </Root>
      );
    },
  },
  listLook("Pfeil-Liste", "v-bl-arrows", { lead: () => <Ic n="right" /> }),
  listLook("Balken links", "v-bl-bars"),
  listLook("Randlinie mit Zählern", "v-bl-rail", { ol: true, lead: (i) => <span className="v-bl-c" aria-hidden="true">{i + 1}</span> }),
];

/* ---------- Kernsatz ---------- */

function quoteLook(name: string, cls: string, fits?: (b: B<"quote">) => boolean, before?: React.ReactNode): Look<"quote"> {
  return {
    name, fits,
    View: function QuoteLook({ b, p, limits }) {
      return <Root cls={cls}>{before}<Txt path={`${p}.text`} value={b.text} as="p" max={limits.item} /></Root>;
    },
  };
}

const QUOTES: Look<"quote">[] = [
  quoteLook("Großes Zitat", "v-qt-big", undefined, QUOTE),
  quoteLook("Zwischen Linien", "v-qt-lines"),
  {
    name: "Schlüsselwort",
    // The keyword must still stand in the sentence, a translation may have lost it.
    fits: (b) => !!b.keyword && b.text.toLowerCase().includes(b.keyword.toLowerCase()),
    View: function KeywordQuote({ b, p, limits }) {
      const { editing } = useContext(EditCtx);
      const kw = b.keyword ?? "";
      const at = kw ? b.text.toLowerCase().indexOf(kw.toLowerCase()) : -1;
      // While editing the whole sentence is one field; readers get the word underlined.
      return (
        <Root cls="v-qt-under">
          {editing || at < 0 ? (
            <Txt path={`${p}.text`} value={b.text} as="p" max={limits.item} />
          ) : (
            <p>
              {b.text.slice(0, at)}
              <span className="v-qt-kw">{b.text.slice(at, at + kw.length)}</span>
              {b.text.slice(at + kw.length)}
            </p>
          )}
        </Root>
      );
    },
  },
];

/* ---------- Checkliste ---------- */

function checkLook(name: string, cls: string, opts: { fits?: (b: B<"checklist">) => boolean; lead: (i: number) => React.ReactNode; tail?: boolean; ol?: boolean }): Look<"checklist"> {
  return {
    name, fits: opts.fits,
    View: function CheckLook({ b, p, limits }) {
      const Tag = opts.ol ? "ol" : "ul";
      return (
        <Root>
          <Tag className={cls}>
            {b.items.map((v, i) => (
              <li key={i} data-d={`${p}.items.${i}`}>
                {opts.lead(i)}
                <Txt path={`${p}.items.${i}`} value={v} as="span" max={limits.item} />
                {opts.tail && <Ic n="check" />}
              </li>
            ))}
          </Tag>
          <AddItem p={p} n={b.items.length} limits={limits} />
        </Root>
      );
    },
  };
}

const CHECKLIST: Look<"checklist">[] = [
  checkLook("Kästchen mit Haken", "v-ck-box", { lead: () => <span className="v-ck-sq"><Ic n="check" /></span> }),
  checkLook("Zweispaltig", "v-ck-two", { fits: (b) => b.items.length >= 4, lead: () => <span className="v-ck-dot"><Ic n="check" /></span> }),
  checkLook("Nummeriert mit Linie", "v-ck-num", { ol: true, tail: true, lead: (i) => <span className="v-ck-i" aria-hidden="true">{two(i)}</span> }),
];

/* ---------- Begriffe ---------- */

function pairsLook(name: string, cls: string, fits?: (b: B<"definitions">) => boolean): Look<"definitions"> {
  return {
    name, fits,
    View: function PairsLook({ b, p, limits }) {
      return (
        <Root>
          <dl className={cls}>
            {b.items.map((d, i) => (
              <div key={i} data-d={`${p}.items.${i}`}>
                <Txt path={`${p}.items.${i}.term`} value={d.term} as="dt" max={limits.short} />
                <Txt path={`${p}.items.${i}.text`} value={d.text} as="dd" max={limits.item} />
              </div>
            ))}
          </dl>
          <AddItem p={p} n={b.items.length} limits={limits} />
        </Root>
      );
    },
  };
}

/** Inline looks: the term and its text follow each other inside one paragraph. */
function inlineLook(name: string, cls: string, termCls: string, fits?: (b: B<"definitions">) => boolean, textAs: "span" | "i" = "span"): Look<"definitions"> {
  return {
    name, fits,
    View: function InlineLook({ b, p, limits }) {
      return (
        <Root cls={cls}>
          {b.items.map((d, i) => (
            <p key={i} data-d={`${p}.items.${i}`}>
              <Txt path={`${p}.items.${i}.term`} value={d.term} as="b" className={termCls} max={limits.short} />
              {" "}
              <Txt path={`${p}.items.${i}.text`} value={d.text} as={textAs} max={limits.item} />
            </p>
          ))}
          <AddItem p={p} n={b.items.length} limits={limits} />
        </Root>
      );
    },
  };
}

const DEFINITIONS: Look<"definitions">[] = [
  pairsLook("Tabelle", "v-df-table"),
  {
    name: "Glossar",
    View: function Glossary({ b, p, limits }) {
      // Sorted for reading only, every entry keeps its own path.
      const sorted = b.items.map((d, i) => ({ d, i })).sort((x, y) => x.d.term.localeCompare(y.d.term, undefined, { sensitivity: "base" }));
      const groups: { letter: string; list: typeof sorted }[] = [];
      for (const e of sorted) {
        const letter = e.d.term.charAt(0).toUpperCase();
        const g = groups[groups.length - 1];
        if (g && g.letter === letter) g.list.push(e); else groups.push({ letter, list: [e] });
      }
      return (
        <Root cls="v-df-gloss">
          {groups.map((g) => (
            <div key={g.letter}>
              <span className="v-df-letter" aria-hidden="true">{g.letter}</span>
              <div>
                {g.list.map(({ d, i }) => (
                  <div className="v-df-e" key={i} data-d={`${p}.items.${i}`}>
                    <Txt path={`${p}.items.${i}.term`} value={d.term} as="b" max={limits.short} />
                    <Txt path={`${p}.items.${i}.text`} value={d.text} as="span" max={limits.item} />
                  </div>
                ))}
              </div>
            </div>
          ))}
          <AddItem p={p} n={b.items.length} limits={limits} />
        </Root>
      );
    },
  },
  pairsLook("Begriff darüber", "v-df-stack"),
  inlineLook("Etikett", "v-df-tags", "v-df-tag", (b) => b.items.every((d) => d.term.length <= 30)),
  pairsLook("Akzentspalte", "v-df-spine"),
  inlineLook("Wörterbuch", "v-df-dict", "v-df-term", undefined, "i"),
];

/* ---------- Karten ---------- */

// Only signs that tell cards apart, "none" and the old "info" draw nothing.
const ICONS: Partial<Record<CardIcon, typeof Check>> = { check: Check, x: X, warning: Warning, idea: Lightbulb };
const real = (c: { icon: CardIcon }) => (ICONS[c.icon] ? c.icon : "none");
/** A sign that every card carries says nothing, so signs show only when they differ. */
const differ = (b: B<"cards">) => new Set(b.cards.map(real)).size > 1;

function Sign({ icon, ring }: { icon: CardIcon; ring?: boolean }) {
  const I = ICONS[icon];
  if (!I) return null;
  return <span className={`${ring ? "v-cd-ring" : "v-cd-sign"} ${icon}`}><I size={ring ? 20 : 15} weight="bold" aria-hidden="true" /></span>;
}

/**
 * Column classes on a six-column grid, so the last row is never one card alone: two cards share
 * a row of their own, centred at the bottom or, with top set, wide across the first row.
 */
function spans(n: number, top: boolean): string[] {
  const rem = n % 3;
  return Array.from({ length: n }, (_, i) => {
    if (n === 1) return "v-cd-s6";
    if (n === 2) return "v-cd-s3";
    if (rem === 0) return "v-cd-s2";
    if (rem === 1) return (top ? i < 4 : i >= n - 4) ? "v-cd-s3" : "v-cd-s2";
    if (top) return i < 2 ? "v-cd-s3" : "v-cd-s2";
    return i === n - 2 ? "v-cd-c2" : i === n - 1 ? "v-cd-c4" : "v-cd-s2";
  });
}

function Card({ c, p, i, limits, cls, lead, sign }: { c: B<"cards">["cards"][number]; p: string; i: number; limits: Limits; cls?: string; lead?: React.ReactNode; sign: boolean }) {
  const title = <Txt path={`${p}.cards.${i}.title`} value={c.title} as="h3" max={limits.short} />;
  const text = <Txt path={`${p}.cards.${i}.text`} value={c.text} as="p" max={limits.item} />;
  const head = sign ? <div className="v-cd-head"><Sign icon={c.icon} />{title}</div> : title;
  return (
    <div className={`v-cd-card${cls ? ` ${cls}` : ""}`} data-d={`${p}.cards.${i}`}>
      {lead ? <>{lead}<div>{head}{text}</div></> : <>{head}{text}</>}
    </div>
  );
}

function cardsLook(name: string, cls: string, opts: { fits?: (b: B<"cards">) => boolean; top?: boolean; grid?: boolean; lead?: (c: B<"cards">["cards"][number], i: number) => React.ReactNode; style?: (n: number) => React.CSSProperties }): Look<"cards"> {
  return {
    name, fits: opts.fits,
    View: function CardsLook({ b, p, limits }) {
      const n = b.cards.length;
      const cols = opts.grid ? spans(n, !!opts.top) : [];
      const sign = !opts.lead && differ(b);
      return (
        <Root>
          <div className={cls} style={opts.style?.(n)}>
            {b.cards.map((c, i) => <Card key={i} c={c} p={p} i={i} limits={limits} cls={cols[i]} lead={opts.lead?.(c, i)} sign={sign} />)}
          </div>
          <AddItem p={p} n={n} limits={limits} />
        </Root>
      );
    },
  };
}

const CARDS: Look<"cards">[] = [
  cardsLook("Raster 3+2", "v-cd-grid", { grid: true }),
  cardsLook("Rahmen", "v-cd-row", { grid: true, fits: (b) => b.cards.length <= 5, style: (n) => ({ "--v-cd-n": n } as React.CSSProperties) }),
  cardsLook("Kante oben", "v-cd-edge", {}),
  cardsLook("Nummeriert", "v-cd-rows", { lead: (c, i) => <span className="v-cd-no" aria-hidden="true">{two(i)}</span> }),
  cardsLook("Icon-Zeichen", "v-cd-icons", {
    grid: true, top: true,
    fits: (b) => b.cards.every((c) => real(c) !== "none") && differ(b),
    lead: (c) => <Sign icon={c.icon} ring />,
  }),
];

/* ---------- Akkordeon ---------- */

/** True while the page prints, so every fold is open on paper. */
function usePrinting() {
  const [printing, setPrinting] = useState(false);
  useEffect(() => {
    const on = () => setPrinting(true), off = () => setPrinting(false);
    window.addEventListener("beforeprint", on);
    window.addEventListener("afterprint", off);
    return () => { window.removeEventListener("beforeprint", on); window.removeEventListener("afterprint", off); };
  }, []);
  return printing;
}

const PLUS = (
  <svg className="v-ac-ic" viewBox="0 0 18 18" aria-hidden="true"><path className="v-ac-h" d="M3 9h12" /><path className="v-ac-v" d="M9 3v12" /></svg>
);
const CHEV = <svg className="v-ac-ch" viewBox="0 0 18 18" aria-hidden="true"><path d="M5 7l4 4 4-4" /></svg>;

/** The folds of an accordion; while editing all stay open so every text can be typed in. */
interface FoldsProps {
  items: B<"accordion">["items"];
  p: string;
  limits: Limits;
  /** The index of the first item, the two-column look hands over a slice. */
  from?: number;
  /** The first fold starts open for readers. */
  first?: boolean;
  numbers?: boolean;
  chevron?: boolean;
}
function Folds({ items, p, limits, from = 0, first, numbers, chevron }: FoldsProps) {
  const { editing } = useContext(EditCtx);
  const printing = usePrinting();
  return (
    <>
      {items.map((x, k) => {
        const i = from + k;
        return (
          <details key={i} data-d={`${p}.items.${i}`} open={editing || printing || (first && i === 0) || undefined}>
            <summary onClick={(e) => { if (editing) e.preventDefault(); }}>
              {numbers && <b aria-hidden="true">{two(i)}</b>}
              <Txt path={`${p}.items.${i}.title`} value={x.title} as="span" max={limits.short} />
              {chevron ? CHEV : PLUS}
            </summary>
            <Txt path={`${p}.items.${i}.text`} value={x.text} as="p" max={limits.item} />
          </details>
        );
      })}
    </>
  );
}

function foldsLook(name: string, cls: string, opts: Pick<FoldsProps, "first" | "numbers" | "chevron"> = {}): Look<"accordion"> {
  return {
    name,
    View: function FoldsLook({ b, p, limits }) {
      return (
        <Root>
          <div className={`v-ac ${cls}`}><Folds items={b.items} p={p} limits={limits} {...opts} /></div>
          <AddItem p={p} n={b.items.length} limits={limits} />
        </Root>
      );
    },
  };
}

const ACCORDION: Look<"accordion">[] = [
  foldsLook("Schlicht mit Plus", "v-ac-plain"),
  foldsLook("Nummeriert", "v-ac-num", { numbers: true, chevron: true }),
  foldsLook("Rahmen, erstes offen", "v-ac-box", { first: true, chevron: true }),
  {
    name: "Zwei Spalten",
    View: function TwoFolds({ b, p, limits }) {
      const half = Math.ceil(b.items.length / 2);
      return (
        <Root>
          <div className="v-ac v-ac-two">
            <div><Folds items={b.items.slice(0, half)} p={p} limits={limits} /></div>
            <div><Folds items={b.items.slice(half)} p={p} limits={limits} from={half} /></div>
          </div>
          <AddItem p={p} n={b.items.length} limits={limits} />
        </Root>
      );
    },
  },
  {
    name: "Reiter links",
    View: function Tabs({ b, p, limits }) {
      const { editing } = useContext(EditCtx);
      const printing = usePrinting();
      const [on, setOn] = useState(0);
      const cur = on < b.items.length ? on : 0;
      const all = editing || printing;
      return (
        <Root>
          <div className="v-ac v-ac-tabs">
            <div className="v-ac-list" role="tablist">
              {b.items.map((x, i) => (
                <button key={i} type="button" role="tab" aria-selected={cur === i} className={cur === i ? "on" : undefined} onClick={() => setOn(i)}>
                  {x.title}
                </button>
              ))}
            </div>
            <div>
              {b.items.map((x, i) => (
                <div className="v-ac-pane" key={i} data-d={`${p}.items.${i}`} role="tabpanel" hidden={!all && cur !== i}>
                  <Txt path={`${p}.items.${i}.title`} value={x.title} as="h3" max={limits.short} />
                  <Txt path={`${p}.items.${i}.text`} value={x.text} as="p" max={limits.item} />
                </div>
              ))}
            </div>
          </div>
          <AddItem p={p} n={b.items.length} limits={limits} />
        </Root>
      );
    },
  },
];

export const LOOKS_TEXT: Looks = {
  text: TEXT,
  bullets: BULLETS,
  quote: QUOTES,
  checklist: CHECKLIST,
  definitions: DEFINITIONS,
  cards: CARDS,
  accordion: ACCORDION,
};

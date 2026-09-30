"use client";

import { Image as ImageIcon } from "@phosphor-icons/react";
import { useTranslations } from "next-intl";
import type { Skizze } from "../_logic";
import type { Body, Card, Column, Entry, Figure, SymbolItem } from "../_types";

interface FolienSkizzeProps {
  nummer: number;
  /** Null for a placeholder while the outline is still being planned. */
  skizze: Skizze | null;
  deckTitel: string;
  untertitel: string;
  vortragend: string;
  /** The picture slots of this slide that are already drawn. */
  bilder: string[];
  bildUrl: (slot: string) => string;
  /** While the run goes on a gap is still coming, afterwards it stays a gap. */
  laeuft: boolean;
}

// The body text fades out at the bottom instead of being cut mid-line.
const AUSBLENDEN = "[mask-image:linear-gradient(to_bottom,black_78%,transparent)]";

/** A grey bar for text that is not written yet. */
export function Balken({ laeuft, className = "" }: { laeuft: boolean; className?: string }) {
  return <span aria-hidden="true" className={`block h-2 rounded-sm bg-surface-dim ${laeuft ? "animate-pulse" : ""} ${className}`} />;
}

function BildFeld({ url, laeuft, className = "" }: { url: string | null; laeuft: boolean; className?: string }) {
  const t = useTranslations("tools.praesentation.slides");
  if (url) {
    // eslint-disable-next-line @next/next/no-img-element
    return <img src={url} alt="" className={`block w-full h-full min-h-0 object-cover rounded-sm animate-[fadeIn_0.4s_ease-out] ${className}`} />;
  }
  return (
    <span className={`flex items-center justify-center min-h-0 rounded-sm bg-surface-dim ${laeuft ? "animate-pulse" : ""} ${className}`}>
      {laeuft
        ? <ImageIcon className="w-5 h-5 text-muted-soft" aria-hidden="true" />
        : <span className="text-3xs text-muted">{t("imageMissing")}</span>}
    </span>
  );
}

function Punkte({ items }: { items: string[] }) {
  return (
    <ul className="list-disc pl-3.5 space-y-0.5">
      {items.map((x, i) => <li key={i}>{x}</li>)}
    </ul>
  );
}

function Spalten({ columns }: { columns: Column[] }) {
  return (
    <div className="grid grid-cols-2 gap-3">
      {columns.map((c, i) => (
        <div key={i} className="min-w-0">
          {c.heading && <p className="font-semibold text-foreground truncate">{c.heading}</p>}
          <Punkte items={c.items} />
        </div>
      ))}
    </div>
  );
}

function Tabelle({ header, rows }: { header: string[]; rows: string[][] }) {
  return (
    <table className="w-full table-fixed border-collapse">
      {header.length > 0 && (
        <thead>
          <tr>{header.map((h, i) => <th key={i} className="text-left font-semibold text-foreground px-1 py-0.5 border-b-2 border-border truncate">{h}</th>)}</tr>
        </thead>
      )}
      <tbody>
        {rows.map((r, i) => (
          <tr key={i}>{r.map((c, j) => <td key={j} className="px-1 py-0.5 border-b border-border-soft truncate">{c}</td>)}</tr>
        ))}
      </tbody>
    </table>
  );
}

/** Chart and bar slides alike as a row of labelled bars, the length follows the value. */
function Balkenreihe({ eintraege }: { eintraege: { label: string; value: number }[] }) {
  const hoechster = Math.max(1, ...eintraege.map((e) => Math.abs(e.value)));
  return (
    <div className="space-y-1">
      {eintraege.map((e, i) => (
        <div key={i} className="flex items-center gap-2">
          <span className="w-1/3 truncate">{e.label}</span>
          <span className="flex-1 h-2 rounded-sm bg-kb/10">
            <span className="block h-full rounded-sm bg-kb" style={{ width: `${Math.max(4, (Math.abs(e.value) / hoechster) * 100)}%` }} />
          </span>
        </div>
      ))}
    </div>
  );
}

function Karten({ cards }: { cards: Card[] }) {
  return (
    <div className="grid gap-1.5" style={{ gridTemplateColumns: `repeat(${Math.min(Math.max(cards.length, 1), 3)}, minmax(0, 1fr))` }}>
      {cards.map((c, i) => (
        <div key={i} className="rounded-sm bg-kb/10 p-1.5 min-w-0">
          <p className="font-semibold text-foreground truncate">{c.title}</p>
          <p className="line-clamp-2">{c.text}</p>
        </div>
      ))}
    </div>
  );
}

/** A few entries side by side, as many columns as there are entries. */
const nebeneinander = (n: number) => ({ gridTemplateColumns: `repeat(${Math.max(n, 1)}, minmax(0, 1fr))` });

function Schritte({ steps }: { steps: Entry[] }) {
  return (
    <div className="grid gap-2" style={nebeneinander(steps.length)}>
      {steps.map((e, i) => (
        <div key={i} className="min-w-0 flex flex-col items-center text-center gap-0.5">
          <span className="w-4 h-4 rounded-full bg-kb text-white text-3xs font-bold flex items-center justify-center">{i + 1}</span>
          <p className="font-semibold text-foreground truncate w-full">{e.title}</p>
          <p className="line-clamp-2">{e.text}</p>
        </div>
      ))}
    </div>
  );
}

/** The highest level on top and in full colour, each level below a little wider and lighter. */
function Stufen({ levels }: { levels: Entry[] }) {
  return (
    <div className="space-y-1">
      {levels.map((e, i) => (
        <div key={i} className="flex items-center gap-2">
          <span className="w-1/4 shrink-0 flex justify-center">
            <span className="block h-3 rounded-sm bg-kb"
                  style={{ width: `${((i + 1) / levels.length) * 100}%`, opacity: 1 - (i / Math.max(levels.length, 1)) * 0.6 }} />
          </span>
          <p className="min-w-0 truncate"><span className="font-semibold text-foreground">{e.title}</span> {e.text}</p>
        </div>
      ))}
    </div>
  );
}

function Kennzahlen({ figures }: { figures: Figure[] }) {
  return (
    <div className="grid gap-2 pt-2" style={nebeneinander(figures.length)}>
      {figures.map((f, i) => (
        <div key={i} className="min-w-0 text-center">
          <p className="text-base font-bold text-kb truncate">{f.value}</p>
          <p className="line-clamp-2">{f.label}</p>
        </div>
      ))}
    </div>
  );
}

// The icon names come from the template's icon set, the sketch stands in with the first letter.
function Symbole({ symbols }: { symbols: SymbolItem[] }) {
  return (
    <div className="grid gap-2" style={nebeneinander(Math.min(symbols.length, 4))}>
      {symbols.map((x, i) => (
        <div key={i} className="min-w-0 flex flex-col items-center text-center gap-0.5">
          <span className="w-5 h-5 rounded-full bg-kb/10 text-kb text-3xs font-bold flex items-center justify-center">
            {x.label.trim().charAt(0).toUpperCase()}
          </span>
          <p className="truncate w-full">{x.label}</p>
        </div>
      ))}
    </div>
  );
}

function Inhalt({ body, columns }: { body: Body | null; columns: Column[] }) {
  if (columns.length > 0) return <Spalten columns={columns} />;
  if (!body) return null;
  switch (body.kind) {
    case "bullets": return <Punkte items={body.items} />;
    case "table": return <Tabelle header={body.header} rows={body.rows} />;
    case "chart": return <Balkenreihe eintraege={body.categories.map((c, i) => ({ label: c, value: body.series[0]?.values[i] ?? 0 }))} />;
    case "bars": return <Balkenreihe eintraege={body.bars.map((b) => ({ label: b.label, value: b.value }))} />;
    case "cards": return <Karten cards={body.cards} />;
    case "steps": return <Schritte steps={body.steps ?? []} />;
    case "levels": return <Stufen levels={body.levels ?? []} />;
    case "figures": return <Kennzahlen figures={body.figures ?? []} />;
    case "symbols": return <Symbole symbols={body.symbols ?? []} />;
    case "highlight":
      return (
        <div className="flex items-center gap-3">
          <span className="shrink-0 rounded-sm bg-kb text-white font-bold text-sm px-2 py-1.5">{body.key}</span>
          <p>{body.text}</p>
        </div>
      );
    // Kinds the sketch has no drawing for still show their words.
    default:
      if (body.items.length > 0) return <Punkte items={body.items} />;
      return body.text ? <p>{body.text}</p> : null;
  }
}

/** The slide drawn from what is known so far: planned title and gist first, then text and pictures. */
function Flaeche(p: FolienSkizzeProps) {
  const k = p.skizze;
  const l = p.laeuft;
  if (!k) {
    return p.nummer === 1 ? (
      <div className="h-full flex flex-col items-center justify-center gap-2 p-4">
        <Balken laeuft={l} className="h-3 w-1/2" />
        <Balken laeuft={l} className="w-1/3" />
        {p.vortragend && <p className="text-3xs text-muted mt-1">{p.vortragend}</p>}
      </div>
    ) : (
      <div className="h-full flex flex-col gap-2 p-4">
        <Balken laeuft={l} className="h-3 w-2/3" />
        <Balken laeuft={l} className="mt-1 w-11/12" />
        <Balken laeuft={l} className="w-4/5" />
        <Balken laeuft={l} className="w-3/5" />
      </div>
    );
  }

  const s = k.slide;
  const url = (slot: string) => (p.bilder.includes(slot) ? p.bildUrl(slot) : null);
  const titel = s?.title || k.row?.title || (k.role === "deckblatt" ? p.deckTitel : "");
  // Cover, section and closing slides of many templates carry a picture above their title.
  const bildOben = s && s.images.length > 0 ? <BildFeld url={url("0")} laeuft={l} className="flex-1 w-full" /> : null;
  const titelZeile = titel
    ? <p className="text-sm font-bold text-foreground leading-snug line-clamp-2">{titel}</p>
    : <Balken laeuft={l} className="h-3 w-2/3" />;

  if (k.role === "deckblatt") {
    return (
      <div className="h-full flex flex-col items-center justify-center gap-1 p-4 text-center">
        {bildOben && <div className="flex-1 w-full min-h-0 flex mb-2">{bildOben}</div>}
        {titel ? <p className="text-base font-bold text-foreground leading-snug line-clamp-3">{titel}</p> : <Balken laeuft={l} className="h-3 w-1/2" />}
        {(s?.subtitle || p.untertitel) && <p className="text-2xs text-foreground-soft line-clamp-2">{s?.subtitle || p.untertitel}</p>}
        {p.vortragend && <p className="text-3xs text-muted mt-1">{p.vortragend}</p>}
      </div>
    );
  }
  if (k.role === "abschnitt" || k.role === "abschluss") {
    return (
      <div className={`h-full flex flex-col justify-center gap-1.5 p-4 ${k.role === "abschluss" ? "items-center text-center" : ""}`}>
        {bildOben && <div className="flex-1 w-full min-h-0 flex mb-1">{bildOben}</div>}
        {titel ? <p className="text-base font-bold text-foreground leading-snug line-clamp-3">{titel}</p> : <Balken laeuft={l} className="h-3 w-1/2" />}
        {!s && k.row?.gist && <p className="text-2xs italic text-muted line-clamp-2">{k.row.gist}</p>}
      </div>
    );
  }

  // Before the text is written only the role tells whether a picture is coming.
  const seitenBilder = s ? s.images.map((_, i) => String(i)) : k.role === "text_mit_bild" || k.role === "bild_gross" ? ["0"] : [];
  const gross = k.role === "bild_gross";
  const textFeld = s ? (
    s.body?.kind === "image"
      ? <BildFeld url={url("body")} laeuft={l} className="h-full" />
      : <Inhalt body={s.body} columns={s.columns} />
  ) : (
    <div className="space-y-1.5">
      {k.row?.gist && <p className="italic text-muted line-clamp-2">{k.row.gist}</p>}
      <Balken laeuft={l} className="w-11/12" />
      <Balken laeuft={l} className="w-4/5" />
      <Balken laeuft={l} className="w-3/5" />
    </div>
  );

  return (
    <div className="h-full flex flex-col gap-2 p-4">
      {titelZeile}
      <div className="flex-1 min-h-0 flex gap-3">
        {!gross && (
          <div className={`flex-1 min-w-0 overflow-hidden text-2xs leading-snug text-foreground-soft ${AUSBLENDEN}`}>{textFeld}</div>
        )}
        {seitenBilder.length > 0 && (
          <div className={`flex flex-col gap-2 min-h-0 ${gross ? "flex-1" : "w-2/5 shrink-0"}`}>
            {seitenBilder.map((slot) => <BildFeld key={slot} url={url(slot)} laeuft={l} className="flex-1" />)}
          </div>
        )}
      </div>
    </div>
  );
}

/** The slide drawn from what is known so far, it stands where the preview goes until that is rendered. */
export default function FolienSkizze(p: FolienSkizzeProps) {
  return (
    <div className="aspect-video overflow-hidden rounded-md border-2 border-border bg-background">
      <Flaeche {...p} />
    </div>
  );
}

"use client";

import type { ReactNode } from "react";
import { useTranslations } from "next-intl";
import { Txt } from "../Txt";
import type { Look, LookProps } from "./registry";
import { Caption, Grow } from "./shared";

type CellRender = (c: string, j: number, txt: ReactNode) => ReactNode;

function TableLook({ b, p, limits, num, cls, cell }: LookProps<"table"> & { cls: string; cell?: CellRender }) {
  const t = useTranslations("tools.pages");
  const S = limits.short;
  // A row head column of short entries stays on one line and takes only its own width.
  const tight = b.rows.every((r) => (r[0] ?? "").length <= 24);
  return (
    <figure className="v-nu-root">
      <div className={`v-nu-tb ${cls}${tight ? " v-nu-tb-tight" : ""}`}>
        <table>
          <thead>
            <tr>{b.header.map((h, i) => <th key={i} scope="col"><Txt path={`${p}.header.${i}`} value={h} as="div" max={S} keep /></th>)}</tr>
          </thead>
          <tbody>
            {b.rows.map((r, i) => (
              <tr key={i} data-d={`${p}.rows.${i}`}>
                {r.map((c, j) => {
                  const txt = <Txt path={`${p}.rows.${i}.${j}`} value={c} as="div" max={S} keep />;
                  return j === 0
                    ? <th key={j} scope="row" data-h={b.header[0]}>{txt}</th>
                    : <td key={j} data-h={b.header[j]}>{cell ? cell(c, j, txt) : txt}</td>;
                })}
              </tr>
            ))}
          </tbody>
        </table>
        <Grow items={[
          { what: "row", path: p, full: b.rows.length >= limits.tableRows, label: t("addRow"), limit: t("maxRows", { max: limits.tableRows }) },
          { what: "col", path: p, full: b.header.length >= limits.tableCols, label: t("addCol"), limit: t("maxCols", { max: limits.tableCols }) },
        ]} />
      </div>
      <Caption p={p} b={b} num={num} kind="table" limits={limits} />
    </figure>
  );
}

/** A whole number from 0 to 10 in a cell, any other text gives null. */
const smallInt = (s: string) => (/^\s*(10|\d)\s*$/.test(s) ? Number(s) : null);

/** The columns after the first whose cells are all small whole numbers, with the steps of their scale. */
function ratedColumns(b: LookProps<"table">["b"]): (number | null)[] {
  return b.header.map((_, j) => {
    if (j === 0 || b.rows.length < 2) return null;
    const nums = b.rows.map((r) => smallInt(r[j] ?? ""));
    if (nums.some((v) => v === null)) return null;
    const max = Math.max(...nums.map((v) => v ?? 0));
    return max >= 1 ? (max <= 5 ? 5 : 10) : null;
  });
}

const TbPlain = (x: LookProps<"table">) => <TableLook {...x} cls="v-nu-tb-plain" />;
const TbStripe = (x: LookProps<"table">) => <TableLook {...x} cls="v-nu-tb-stripe" />;

function TbDots(x: LookProps<"table">) {
  const rated = ratedColumns(x.b);
  const cell: CellRender = (c, j, txt) => {
    const steps = rated[j];
    if (!steps) return txt;
    const v = smallInt(c) ?? 0;
    return (
      <span className="v-nu-tb-rate">
        <span className="v-nu-tb-lv" role="img" aria-label={c}>
          {Array.from({ length: steps }, (_, k) => <i key={k} className={k < v ? "v-nu-on" : "v-nu-off"} />)}
        </span>
        <span className="v-nu-tb-word">{txt}</span>
      </span>
    );
  };
  return <TableLook {...x} cls="v-nu-tb-dots" cell={cell} />;
}

export const TABLE: Look<"table">[] = [
  { name: "Schlicht mit Kopflinie", family: "grid", View: TbPlain },
  { name: "Gestreift", family: "grid", View: TbStripe },
  { name: "Bewertung mit Punkten", family: "grid", fits: (b) => ratedColumns(b).some(Boolean), View: TbDots },
];

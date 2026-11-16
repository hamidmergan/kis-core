"use client";

import type { Limits } from "../../_lib/types";
import { Txt } from "../Txt";
import type { Look, LookProps } from "./registry";
import { vars } from "./shared";

/** A formula never breaks, its size follows its length so it fits the width it has. */
const fit = (key: string) => vars({ "--fm-len": Math.max(8, key.length) });

/** The formula on one line with its sentence below, shared with the old highlight. */
function Big({ p, keyText, text, limits }: { p: string; keyText: string; text: string; limits: Limits }) {
  return (
    <div className="v-cp v-fm" style={fit(keyText)}>
      <Txt path={`${p}.key`} value={keyText} as="div" className="v-fm-key" max={limits.short} />
      <Txt path={`${p}.text`} value={text} as="p" className="v-fm-text" max={limits.item} />
    </div>
  );
}

function FmBig({ b, p, limits }: LookProps<"formula">) {
  return <Big p={p} keyText={b.key} text={b.text} limits={limits} />;
}

function FmLegend({ b, p, limits }: LookProps<"formula">) {
  return (
    <div className="v-cp v-fm" style={fit(b.key)}>
      <Txt path={`${p}.key`} value={b.key} as="div" className="v-fm-key" max={limits.short} />
      <dl className="v-fm-parts">
        {b.parts.map((x, i) => (
          <div key={i} data-d={`${p}.parts.${i}`}>
            <Txt path={`${p}.parts.${i}.sym`} value={x.sym} as="dt" max={limits.short} />
            <Txt path={`${p}.parts.${i}.text`} value={x.text} as="dd" max={limits.item} />
          </div>
        ))}
      </dl>
      <Txt path={`${p}.text`} value={b.text} as="p" className="v-fm-text" max={limits.item} />
    </div>
  );
}

function FmWay({ b, p, limits }: LookProps<"formula">) {
  return (
    <div className="v-cp v-fm" style={fit(b.key)}>
      <Txt path={`${p}.key`} value={b.key} as="div" className="v-fm-key" max={limits.short} />
      <ol className="v-fm-lines">
        {b.example.map((l, i) => (
          <li key={i} data-d={`${p}.example.${i}`}>
            <Txt path={`${p}.example.${i}`} value={l} max={limits.item} />
          </li>
        ))}
      </ol>
      <Txt path={`${p}.text`} value={b.text} as="p" className="v-fm-text" max={limits.item} />
    </div>
  );
}

// ---------- highlight of older pages ----------

// A key with an equals sign or an operator between operands is a formula, anything else a term.
const FORMULA_KEY = /=|[+×·÷√^]|\s[-−/]\s/;

function HlLook({ b, p, limits }: LookProps<"highlight">) {
  if (FORMULA_KEY.test(b.key)) return <Big p={p} keyText={b.key} text={b.text} limits={limits} />;
  return (
    <div className="v-cp v-hl">
      <div className="v-hl-term">
        <Txt path={`${p}.key`} value={b.key} as="div" className="v-hl-term-k" max={limits.short} />
        <Txt path={`${p}.text`} value={b.text} as="p" className="v-hl-term-x" max={limits.item} />
      </div>
    </div>
  );
}

export const FORMULA: Look<"formula">[] = [
  { name: "Groß zentriert", View: FmBig },
  { name: "Mit Legende", fits: (b) => b.parts.length > 0, View: FmLegend },
  { name: "Rechenweg", fits: (b) => b.example.length > 0, View: FmWay },
];

export const HIGHLIGHT: Look<"highlight">[] = [{ name: "Formel oder Begriff", View: HlLook }];

"use client";

import { useContext, type ReactNode } from "react";
import { EditCtx, Txt } from "../Txt";
import type { Look, LookProps } from "./registry";
import { Items, usePageWords } from "./shared";

function ExRows({ b, p, limits }: LookProps<"example">) {
  const w = usePageWords();
  const { editing } = useContext(EditCtx);
  const row = (lbl: string, body: ReactNode) => (
    <div className="v-ex-rows-row"><div className="v-ex-rows-lbl">{lbl}</div><div className="v-ex-rows-body">{body}</div></div>
  );
  return (
    <div className="v-cp v-ex-rows">
      <Txt path={`${p}.title`} value={b.title} as="h3" className="v-ex-rows-title" max={limits.short} />
      {(b.situation || editing) && row(w.situation, <Txt path={`${p}.situation`} value={b.situation} as="p" max={limits.item} />)}
      {b.steps.length > 0 && row(w.approach, (
        <ol className="v-ex-rows-steps"><Items p={`${p}.steps`} items={b.steps} max={limits.item} /></ol>
      ))}
      {(b.result || editing) && row(w.result, <Txt path={`${p}.result`} value={b.result} as="p" className="v-ex-rows-res" max={limits.item} />)}
    </div>
  );
}

function ExCalc({ b, p, limits }: LookProps<"example">) {
  return (
    <div className="v-cp v-ex-calc">
      <Txt path={`${p}.title`} value={b.title} as="h3" max={limits.short} />
      <Txt path={`${p}.situation`} value={b.situation} as="p" className="v-ex-calc-sit" max={limits.item} />
      <div className="v-ex-calc-block">
        {b.steps.map((s, i) => (
          <div className="v-ex-calc-line" key={i} data-d={`${p}.steps.${i}`}><Txt path={`${p}.steps.${i}`} value={s} max={limits.item} /></div>
        ))}
        <div className="v-ex-calc-res"><Txt path={`${p}.result`} value={b.result} max={limits.item} /></div>
      </div>
    </div>
  );
}

function ExRail({ b, p, limits }: LookProps<"example">) {
  const w = usePageWords();
  const { editing } = useContext(EditCtx);
  const part = (lbl: string, body: ReactNode, cls = "") => (
    <div className={`v-ex-rail-part ${cls}`}><span className="v-ex-rail-lbl">{lbl}</span>{body}</div>
  );
  return (
    <div className="v-cp v-ex-rail">
      <Txt path={`${p}.title`} value={b.title} as="h3" className="v-ex-rail-title" max={limits.short} />
      <div className="v-ex-rail-line">
        {(b.situation || editing) && part(w.situation, <Txt path={`${p}.situation`} value={b.situation} as="p" max={limits.item} />)}
        {b.steps.length > 0 && part(w.approach, b.steps.map((s, i) => (
          <Txt key={i} path={`${p}.steps.${i}`} value={s} as="p" max={limits.item} />
        )))}
        {(b.result || editing) && part(w.result, <Txt path={`${p}.result`} value={b.result} as="p" max={limits.item} />, "v-ex-rail-res")}
      </div>
    </div>
  );
}

export const EXAMPLE: Look<"example">[] = [
  { name: "Drei Zeilen", View: ExRows },
  { name: "Rechenbeispiel", View: ExCalc },
  { name: "Erzählleiste", View: ExRail },
];

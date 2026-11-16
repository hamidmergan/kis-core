"use client";

import { useNumber } from "../Charts";
import { Txt } from "../Txt";
import { Arrow, Dot, Entry } from "./flow-parts";
import type { Look, LookProps } from "./registry";
import { usePageWords, vars } from "./shared";

function StepsLine({ b, p, limits }: LookProps<"steps">) {
  return (
    <div className="v-fl v-fl-line"><ol className="v-fl-line-list">
      {b.steps.map((s, i) => (
        <li className="v-fl-line-item" key={i} data-d={`${p}.steps.${i}`}>
          <Dot n={i + 1} />
          <Entry p={`${p}.steps.${i}`} e={s} limits={limits} />
        </li>
      ))}
    </ol></div>
  );
}

function StepsStepper({ b, p, limits }: LookProps<"steps">) {
  const fmt = useNumber();
  return (
    <div className="v-fl v-fl-stp"><ol className="v-fl-stp-row" style={vars({ "--n": b.steps.length })}>
      {b.steps.map((s, i) => (
        <li className="v-fl-stp-item" key={i} data-d={`${p}.steps.${i}`}>
          <span className="v-fl-stp-node">{fmt(i + 1)}</span>
          <div className="v-fl-stp-body">
            <Entry p={`${p}.steps.${i}`} e={s} limits={limits} />
          </div>
        </li>
      ))}
    </ol></div>
  );
}

function StepsChevron({ b, p, limits }: LookProps<"steps">) {
  const fmt = useNumber();
  return (
    <div className="v-fl v-fl-chev"><ol className="v-fl-chev-row" style={vars({ "--n": b.steps.length })}>
      {b.steps.map((s, i) => (
        <li className="v-fl-chev-item" key={i} data-d={`${p}.steps.${i}`}>
          <div className="v-fl-chev-box">
            <svg className="v-fl-chev-bg" viewBox="0 0 200 90" preserveAspectRatio="none" aria-hidden="true">
              <path className="v-fl-chev-shape" vectorEffect="non-scaling-stroke" d={i ? "M2 2 L176 2 L198 45 L176 88 L2 88 L24 45 Z" : "M2 2 L176 2 L198 45 L176 88 L2 88 Z"} />
            </svg>
            <span className="v-fl-chev-no">{fmt(i + 1)}</span>
            <Txt path={`${p}.steps.${i}.title`} value={s.title} as="h3" max={limits.short} />
          </div>
          <Txt path={`${p}.steps.${i}.text`} value={s.text} as="p" max={limits.item} />
        </li>
      ))}
    </ol></div>
  );
}

function StepsStair({ b, p, limits }: LookProps<"steps">) {
  const n = Math.max(2, b.steps.length);
  const style = vars({ "--o": Math.min(11, 60 / (n - 1)).toFixed(2), "--op": Math.min(7, 36 / (n - 1)).toFixed(2) });
  return (
    <div className="v-fl v-fl-stair"><ol className="v-fl-stair-list" style={style}>
      {b.steps.map((s, i) => (
        <li className="v-fl-stair-step" key={i} data-d={`${p}.steps.${i}`} style={vars({ "--i": i })}>
          <Dot n={i + 1} />
          <div>
            <Entry p={`${p}.steps.${i}`} e={s} limits={limits} />
          </div>
        </li>
      ))}
    </ol></div>
  );
}

function StepsBig({ b, p, limits }: LookProps<"steps">) {
  const fmt = useNumber();
  const n = b.steps.length;
  // Up to six stand in one row, seven and eight break into rows of four.
  const cols = n <= 6 ? n : 4;
  return (
    <div className="v-fl v-fl-big"><ol className="v-fl-big-row" style={vars({ "--n": cols })}>
      {b.steps.map((s, i) => (
        <li className={`v-fl-big-col${i % cols === 0 ? " v-fl-big-first" : ""}${i >= cols ? " v-fl-big-more" : ""}`} key={i} data-d={`${p}.steps.${i}`}>
          <span className="v-fl-big-no">{fmt(i + 1)}</span>
          <div>
            <Entry p={`${p}.steps.${i}`} e={s} limits={limits} />
          </div>
        </li>
      ))}
    </ol></div>
  );
}

function StepsZig({ b, p, limits }: LookProps<"steps">) {
  return (
    <div className="v-fl v-fl-zig"><ol className="v-fl-zig-grid">
      {b.steps.map((s, i) => (
        <li className={`v-fl-zig-item ${i % 2 ? "v-fl-zig-r" : "v-fl-zig-l"}`} key={i} data-d={`${p}.steps.${i}`} style={{ gridRow: i + 1 }}>
          <Entry p={`${p}.steps.${i}`} e={s} limits={limits} />
        </li>
      ))}
      {b.steps.map((_, i) => (
        <li className="v-fl-zig-mark" key={`m${i}`} style={{ gridRow: i + 1 }} aria-hidden="true"><Dot n={i + 1} /></li>
      ))}
    </ol></div>
  );
}

function StepsIndex({ b, p, limits }: LookProps<"steps">) {
  const fmt = useNumber();
  return (
    <div className="v-fl v-fl-idx"><ol className="v-fl-idx-list">
      {b.steps.map((s, i) => (
        <li className="v-fl-idx-row" key={i} data-d={`${p}.steps.${i}`}>
          <span className="v-fl-idx-no">{fmt(i + 1).padStart(2, "0")}</span>
          <div>
            <Entry p={`${p}.steps.${i}`} e={s} limits={limits} />
          </div>
        </li>
      ))}
    </ol></div>
  );
}

/** Rows of at most three stations, never one alone. */
function flowRows(n: number): number[] {
  const rows: number[] = [];
  let left = n;
  while (left > 3) {
    if (left === 4) { rows.push(2, 2); left = 0; } else { rows.push(3); left -= 3; }
  }
  if (left > 0) rows.push(left);
  return rows;
}

function StepsFlow({ b, p, limits }: LookProps<"steps">) {
  const fmt = useNumber();
  const w = usePageWords();
  const rows = flowRows(b.steps.length);
  // The centre of a station in a row of three or two, measured from the row's edge.
  const edge = (k: number) => (k === 3 ? "calc(16.667% - 16px)" : "calc(33.333% - 8px)");
  let at = 0;
  return (
    <div className="v-fl v-fl-flow">
      {rows.map((k, r) => {
        const first = at;
        at += k;
        return (
          <div key={r}>
            {r > 0 && (
              <>
                <div className="v-fl-flow-elbow" aria-hidden="true" style={vars({ "--el": edge(k), "--er": edge(rows[r - 1]) })}><i /></div>
                <div className="v-fl-flow-down" aria-hidden="true"><Arrow /></div>
              </>
            )}
            <ol className="v-fl-flow-row">
              {b.steps.slice(first, first + k).map((s, j) => {
                const i = first + j;
                return (
                  <li className="v-fl-flow-st" key={i} data-d={`${p}.steps.${i}`}>
                    <span className="v-fl-flow-no">{`${w.step} ${fmt(i + 1)}`}</span>
                    <Entry p={`${p}.steps.${i}`} e={s} limits={limits} />
                  </li>
                );
              }).flatMap((el, j) => (j ? [<li className="v-fl-flow-a" key={`a${first + j}`} aria-hidden="true"><Arrow /></li>, el] : [el]))}
            </ol>
          </div>
        );
      })}
    </div>
  );
}

export const STEPS: Look<"steps">[] = [
  { name: "Senkrechte Linie", View: StepsLine },
  { name: "Stepper", fits: (b) => b.steps.length <= 6, View: StepsStepper },
  { name: "Pfeilkette", fits: (b) => b.steps.length >= 3 && b.steps.length <= 6, View: StepsChevron },
  { name: "Treppe", View: StepsStair },
  { name: "Große Ziffern", View: StepsBig },
  { name: "Zickzack", View: StepsZig },
  { name: "Nummer und Text", View: StepsIndex },
  { name: "Fluss", View: StepsFlow },
];

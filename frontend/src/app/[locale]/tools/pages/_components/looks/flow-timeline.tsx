"use client";

import { Txt } from "../Txt";
import { Entry } from "./flow-parts";
import type { Look, LookProps } from "./registry";
import { vars } from "./shared";

/** The first column count whose last row is full or at least half full with two items. */
function colsFor(n: number, prefs: number[]): number {
  return prefs.find((c) => n % c === 0 || (n % c >= 2 && (n % c) * 2 >= c)) ?? prefs[0];
}

function TlVertical({ b, p, limits }: LookProps<"timeline">) {
  return (
    <div className="v-fl v-fl-tl"><ol className="v-fl-tl-list">
      {b.events.map((t, i) => (
        <li className="v-fl-tl-row" key={i} data-d={`${p}.events.${i}`}>
          <Txt path={`${p}.events.${i}.date`} value={t.date} className="v-fl-tl-date" max={limits.short} />
          <span className="v-fl-tl-mark" aria-hidden="true" />
          <div>
            <Entry p={`${p}.events.${i}`} e={t} limits={limits} />
          </div>
        </li>
      ))}
    </ol></div>
  );
}

function TlHorizontal({ b, p, limits }: LookProps<"timeline">) {
  const n = b.events.length;
  return (
    <div className="v-fl v-fl-th"><ol className="v-fl-th-row" style={vars({ "--n": n })}>
      {b.events.map((t, i) => (
        <li className={`v-fl-th-item${i === n - 1 ? " v-fl-th-last" : ""}`} key={i} data-d={`${p}.events.${i}`}>
          <Txt path={`${p}.events.${i}.date`} value={t.date} className="v-fl-th-date" max={limits.short} />
          <span className="v-fl-th-tick" aria-hidden="true" />
          <Entry p={`${p}.events.${i}`} e={t} limits={limits} />
        </li>
      ))}
    </ol></div>
  );
}

function TlZig({ b, p, limits }: LookProps<"timeline">) {
  return (
    <div className="v-fl v-fl-tz"><ol className="v-fl-tz-grid">
      {b.events.map((t, i) => (
        <li className={`v-fl-tz-item ${i % 2 ? "v-fl-tz-r" : "v-fl-tz-l"}`} key={i} data-d={`${p}.events.${i}`} style={{ gridRow: i + 1 }}>
          <Entry p={`${p}.events.${i}`} e={t} limits={limits} />
        </li>
      ))}
      {b.events.map((t, i) => (
        <li className="v-fl-tz-year" key={`y${i}`} style={{ gridRow: i + 1 }}>
          <Txt path={`${p}.events.${i}.date`} value={t.date} max={limits.short} />
        </li>
      ))}
    </ol></div>
  );
}

function TlDiamond({ b, p, limits }: LookProps<"timeline">) {
  const n = b.events.length;
  const cols = n <= 3 ? n : n === 4 ? 2 : n <= 6 ? 3 : 4;
  return (
    <div className="v-fl v-fl-ms"><ol className="v-fl-ms-grid" style={vars({ "--c": cols })}>
      {b.events.map((t, i) => (
        <li className={`v-fl-ms-item${i % cols === 0 ? " v-fl-ms-first" : ""}${i % cols === cols - 1 || i === n - 1 ? " v-fl-ms-end" : ""}`} key={i} data-d={`${p}.events.${i}`}>
          <div className="v-fl-box v-fl-ms-box">
            <svg className="v-fl-ms-svg" viewBox="0 0 72 72" aria-hidden="true"><path className="v-fl-ms-shape" d="M36 3 L69 36 L36 69 L3 36 Z" /></svg>
            <Txt path={`${p}.events.${i}.date`} value={t.date} as="div" className={`v-fl-lbl v-fl-ms-year${t.date.length > 4 ? " v-fl-ms-long" : ""}`} max={limits.short} />
          </div>
          <div>
            <Entry p={`${p}.events.${i}`} e={t} limits={limits} />
          </div>
        </li>
      ))}
    </ol></div>
  );
}

function TlBig({ b, p, limits }: LookProps<"timeline">) {
  const n = b.events.length;
  const cols = colsFor(n, [2, 3, 4]);
  const lastRow = n % cols === 0 ? cols : n % cols;
  return (
    <div className="v-fl v-fl-ty"><ol className="v-fl-ty-grid" style={vars({ "--c": cols })}>
      {b.events.map((t, i) => (
        <li className={`v-fl-ty-item${i >= n - lastRow ? " v-fl-ty-last" : ""}`} key={i} data-d={`${p}.events.${i}`}>
          <Txt path={`${p}.events.${i}.date`} value={t.date} className={`v-fl-ty-year${t.date.length > 5 ? " v-fl-ty-small" : ""}`} max={limits.short} />
          <div>
            <Entry p={`${p}.events.${i}`} e={t} limits={limits} />
          </div>
        </li>
      ))}
    </ol></div>
  );
}

export const TIMELINE: Look<"timeline">[] = [
  { name: "Senkrecht", View: TlVertical },
  { name: "Waagrecht", fits: (b) => b.events.length <= 6, View: TlHorizontal },
  { name: "Wechselseitig", View: TlZig },
  { name: "Meilenstein-Rauten", View: TlDiamond },
  { name: "Große Jahreszahlen", View: TlBig },
];

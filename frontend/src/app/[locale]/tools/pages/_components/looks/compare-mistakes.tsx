"use client";

import { Txt } from "../Txt";
import { Ic } from "./compare-parts";
import type { Look, LookProps } from "./registry";
import { usePageWords, vars } from "./shared";

function MkPairs({ b, p, limits }: LookProps<"mistakes">) {
  return (
    <div className="v-cp v-mk-pair">
      <ul className="v-mk-pair-list">
        {b.pairs.map((m, i) => (
          <li key={i} data-d={`${p}.pairs.${i}`}>
            <div className="v-mk-pair-w"><Ic d="cross" /><Txt path={`${p}.pairs.${i}.wrong`} value={m.wrong} max={limits.item} /></div>
            <div className="v-mk-pair-r"><Ic d="check" /><Txt path={`${p}.pairs.${i}.right`} value={m.right} max={limits.item} /></div>
          </li>
        ))}
      </ul>
    </div>
  );
}

function MkStrike({ b, p, limits }: LookProps<"mistakes">) {
  // Two or four pairs stand in two columns, otherwise three, so five end as three and two.
  const n = b.pairs.length;
  const cols = n <= 2 || n === 4 ? 2 : 3;
  return (
    <div className="v-cp v-mk-strike">
      <div className="v-mk-strike-grid" style={vars({ "--v-cols": cols })}>
        {b.pairs.map((m, i) => (
          <div className="v-mk-strike-item" key={i} data-d={`${p}.pairs.${i}`}>
            <Txt path={`${p}.pairs.${i}.wrong`} value={m.wrong} as="s" max={limits.item} />
            <Txt path={`${p}.pairs.${i}.right`} value={m.right} as="p" max={limits.item} />
          </div>
        ))}
      </div>
    </div>
  );
}

function MkTable({ b, p, limits }: LookProps<"mistakes">) {
  const w = usePageWords();
  return (
    <div className="v-cp v-mk-tab">
      <table className="v-mk-tab-t">
        <thead>
          <tr>
            <th className="v-mk-tab-bad"><span><Ic d="cross" />{w.wrong}</span></th>
            <th className="v-mk-tab-good"><span><Ic d="check" />{w.right}</span></th>
          </tr>
        </thead>
        <tbody>
          {b.pairs.map((m, i) => (
            <tr key={i} data-d={`${p}.pairs.${i}`}>
              <td><Txt path={`${p}.pairs.${i}.wrong`} value={m.wrong} as="div" max={limits.item} keep /></td>
              <td><Txt path={`${p}.pairs.${i}.right`} value={m.right} as="div" max={limits.item} keep /></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function MkArrow({ b, p, limits }: LookProps<"mistakes">) {
  return (
    <div className="v-cp v-mk-arr">
      {b.pairs.map((m, i) => (
        <div className="v-mk-arr-row" key={i} data-d={`${p}.pairs.${i}`}>
          <div className="v-mk-arr-w"><Txt path={`${p}.pairs.${i}.wrong`} value={m.wrong} max={limits.item} /></div>
          <div className="v-mk-arr-a"><Ic d="right" /></div>
          <div className="v-mk-arr-r"><Txt path={`${p}.pairs.${i}.right`} value={m.right} max={limits.item} /></div>
        </div>
      ))}
    </div>
  );
}

export const MISTAKES: Look<"mistakes">[] = [
  { name: "Kreuz und Haken", family: "grid", View: MkPairs },
  { name: "Durchgestrichen", family: "grid", View: MkStrike },
  { name: "Tabelle", family: "grid", View: MkTable },
  { name: "Pfeil", family: "grid", View: MkArrow },
];

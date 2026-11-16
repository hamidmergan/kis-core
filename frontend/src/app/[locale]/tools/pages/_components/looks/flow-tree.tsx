"use client";

import { Txt } from "../Txt";
import type { Look, LookProps } from "./registry";
import { Items, vars } from "./shared";

function TreeOrg({ b, p, limits }: LookProps<"tree">) {
  const n = b.branches.length;
  // The bar runs from the first branch's centre to the last one's; many branches hang their leaves further left.
  const style = vars({ "--n": n, "--bx": `calc(${(50 / n).toFixed(3)}% - ${((8 * (n - 1)) / n).toFixed(1)}px)`, "--lx": n >= 5 ? "30%" : "50%" });
  return (
    <div className="v-fl v-fl-org" style={style}>
      <div className="v-fl-org-root"><Txt path={`${p}.root`} value={b.root} className="v-fl-org-box" max={limits.short} /></div>
      <div className="v-fl-org-bar" aria-hidden="true" />
      <ul className="v-fl-org-branches">
        {b.branches.map((c, i) => (
          <li className="v-fl-org-branch" key={i} data-d={`${p}.branches.${i}`}>
            <Txt path={`${p}.branches.${i}.title`} value={c.title} className="v-fl-org-box" max={limits.short} />
            {c.leaves.length > 0 && (
              <ul className="v-fl-org-leaves">
                <Items p={`${p}.branches.${i}.leaves`} items={c.leaves} max={limits.short} />
              </ul>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}

function TreeIndent({ b, p, limits }: LookProps<"tree">) {
  const half = Math.ceil(b.branches.length / 2);
  const col = (from: number, to: number) => (
    <ul className="v-fl-tree-l1">
      {b.branches.slice(from, to).map((c, j) => {
        const i = from + j;
        return (
          <li key={i} data-d={`${p}.branches.${i}`}>
            <Txt path={`${p}.branches.${i}.title`} value={c.title} className="v-fl-tree-b" max={limits.short} />
            {c.leaves.length > 0 && (
              <ul className="v-fl-tree-l2">
                <Items p={`${p}.branches.${i}.leaves`} items={c.leaves} max={limits.short} />
              </ul>
            )}
          </li>
        );
      })}
    </ul>
  );
  return (
    <div className="v-fl v-fl-tree">
      <Txt path={`${p}.root`} value={b.root} as="div" className="v-fl-tree-root" max={limits.short} />
      {b.branches.length > half && <div className="v-fl-tree-bar" aria-hidden="true" />}
      <div className="v-fl-tree-cols">
        <div className="v-fl-tree-c1">{col(0, half)}</div>
        {b.branches.length > half && <div className="v-fl-tree-c2">{col(half, b.branches.length)}</div>}
      </div>
    </div>
  );
}

function TreeNest({ b, p, limits }: LookProps<"tree">) {
  const n = b.branches.length;
  const cols = n <= 2 ? n : n === 4 ? 2 : 3;
  return (
    <div className="v-fl v-fl-nest"><div className="v-fl-nest-outer">
      <Txt path={`${p}.root`} value={b.root} className="v-fl-nest-legend" max={limits.short} />
      <ul className="v-fl-nest-grid" style={vars({ "--c": cols })}>
        {b.branches.map((c, i) => (
          <li className="v-fl-nest-inner" key={i} data-d={`${p}.branches.${i}`}>
            <Txt path={`${p}.branches.${i}.title`} value={c.title} className="v-fl-nest-legend v-fl-nest-sub" max={limits.short} />
            <ul className="v-fl-nest-leaves">
              <Items p={`${p}.branches.${i}.leaves`} items={c.leaves} max={limits.short} />
            </ul>
          </li>
        ))}
      </ul>
    </div></div>
  );
}

function TreeCols({ b, p, limits }: LookProps<"tree">) {
  const n = b.branches.length;
  const phone = n % 2 === 0 ? 2 : 1;
  return (
    <div className="v-fl v-fl-cols">
      <div className="v-fl-cols-root"><Txt path={`${p}.root`} value={b.root} max={limits.short} /></div>
      <ul className={`v-fl-cols-grid${phone === 1 ? " v-fl-cols-one" : ""}`} style={vars({ "--n": n, "--pc": phone })}>
        {b.branches.map((c, i) => (
          <li className="v-fl-cols-col" key={i} data-d={`${p}.branches.${i}`}>
            <Txt path={`${p}.branches.${i}.title`} value={c.title} as="h3" max={limits.short} />
            <ul>
              <Items p={`${p}.branches.${i}.leaves`} items={c.leaves} max={limits.short} />
            </ul>
          </li>
        ))}
      </ul>
    </div>
  );
}

export const TREE: Look<"tree">[] = [
  { name: "Organigramm", View: TreeOrg },
  { name: "Eingerückter Baum", View: TreeIndent },
  { name: "Verschachtelte Rahmen", View: TreeNest },
  { name: "Spalten je Ast", View: TreeCols },
];

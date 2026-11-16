"use client";

import { Txt } from "../Txt";
import type { Look, LookProps } from "./registry";
import { vars } from "./shared";

/** A figure's value is a number with its unit, never a sentence. */
const VALUE_MAX = 24;

function FigItems({ b, p, limits, cls }: LookProps<"figures"> & { cls: string }) {
  return (
    <>
      {b.figures.map((f, i) => (
        <div className={cls} key={i} data-d={`${p}.figures.${i}`}>
          <Txt path={`${p}.figures.${i}.value`} value={f.value} as="strong" max={VALUE_MAX} />
          <Txt path={`${p}.figures.${i}.label`} value={f.label} as="span" max={limits.short} />
        </div>
      ))}
    </>
  );
}

const shortValues = (n: number) => (b: LookProps<"figures">["b"]) => b.figures.every((f) => f.value.length <= n);

function FigRow(x: LookProps<"figures">) {
  return <div className="v-nu-root"><div className="v-nu-fig-row"><FigItems {...x} cls="v-nu-fig-row-it" /></div></div>;
}

function FigSide({ b, p, limits }: LookProps<"figures">) {
  return (
    <div className="v-nu-root">
      <dl className="v-nu-fig-side">
        {b.figures.map((f, i) => (
          <div className="v-nu-fig-side-it" key={i} data-d={`${p}.figures.${i}`}>
            <Txt path={`${p}.figures.${i}.value`} value={f.value} as="dt" max={VALUE_MAX} />
            <Txt path={`${p}.figures.${i}.label`} value={f.label} as="dd" max={limits.short} />
          </div>
        ))}
      </dl>
    </div>
  );
}

function FigHero({ b, p, limits }: LookProps<"figures">) {
  const [h, ...rest] = b.figures;
  return (
    <div className="v-nu-root">
      <div className="v-nu-fig-hero">
        <div className="v-nu-fig-hero-main" data-d={`${p}.figures.0`}>
          <Txt path={`${p}.figures.0.value`} value={h.value} as="strong" max={VALUE_MAX} />
          <Txt path={`${p}.figures.0.label`} value={h.label} as="span" max={limits.short} />
        </div>
        <div className="v-nu-fig-hero-rest">
          {rest.map((f, k) => (
            <div key={k} data-d={`${p}.figures.${k + 1}`}>
              <Txt path={`${p}.figures.${k + 1}.value`} value={f.value} as="strong" max={VALUE_MAX} />
              <Txt path={`${p}.figures.${k + 1}.label`} value={f.label} as="span" max={limits.short} />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function FigBase(x: LookProps<"figures">) {
  return (
    <div className="v-nu-root">
      <div className="v-nu-fig-base" style={vars({ "--n": x.b.figures.length })}><FigItems {...x} cls="v-nu-fig-base-it" /></div>
    </div>
  );
}

function FigTick(x: LookProps<"figures">) {
  const n = x.b.figures.length;
  // On a phone two columns only when the rows come out full.
  return (
    <div className="v-nu-root">
      <div className="v-nu-fig-tick" style={vars({ "--n": n, "--nc": n % 2 ? 1 : 2 })}><FigItems {...x} cls="v-nu-fig-tick-it" /></div>
    </div>
  );
}

function FigStrip(x: LookProps<"figures">) {
  return (
    <div className="v-nu-root">
      <div className="v-nu-fig-strip" style={vars({ "--n": x.b.figures.length })}><FigItems {...x} cls="v-nu-fig-strip-it" /></div>
    </div>
  );
}

export const FIGURES: Look<"figures">[] = [
  { name: "Reihe mit Trennstrichen", fits: shortValues(14), View: FigRow },
  { name: "Zahl links, Text rechts", View: FigSide },
  { name: "Hauptzahl mit Nebenzahlen", fits: (b) => b.figures.length >= 2 && b.figures[0].value.length <= 12 && shortValues(20)(b), View: FigHero },
  { name: "Zahlen auf Grundlinie", fits: shortValues(14), View: FigBase },
  { name: "Akzentstrich darüber", fits: shortValues(20), View: FigTick },
  { name: "Köpfe einer Leiste", fits: shortValues(16), View: FigStrip },
];

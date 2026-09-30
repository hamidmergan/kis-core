"use client";

import { useState } from "react";

interface Props {
  vorher: string;
  nachher: string;
  labelVorher: string;
  labelNachher: string;
  labelRegler: string;
}

/** The edited picture over the source, a slider uncovers how much of the source shows. */
export default function VorherNachher({ vorher, nachher, labelVorher, labelNachher, labelRegler }: Props) {
  const [anteil, setAnteil] = useState(50);
  return (
    <div className="relative select-none overflow-hidden rounded-md">
      <img src={nachher} alt={labelNachher} className="block w-full" />
      <img
        src={vorher}
        alt={labelVorher}
        className="absolute inset-0 h-full w-full object-cover"
        style={{ clipPath: `inset(0 ${100 - anteil}% 0 0)` }}
      />
      <div className="pointer-events-none absolute inset-y-0 w-0.5 bg-white shadow" style={{ left: `${anteil}%` }} />
      <span className="pointer-events-none absolute left-2 top-2 rounded bg-black/60 px-1.5 py-0.5 text-xs text-white">
        {labelVorher}
      </span>
      <span className="pointer-events-none absolute right-2 top-2 rounded bg-black/60 px-1.5 py-0.5 text-xs text-white">
        {labelNachher}
      </span>
      <input
        type="range"
        min={0}
        max={100}
        value={anteil}
        onChange={(e) => setAnteil(Number(e.target.value))}
        aria-label={labelRegler}
        className="absolute inset-0 h-full w-full cursor-ew-resize opacity-0"
      />
    </div>
  );
}

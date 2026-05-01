"use client";

import { useState } from "react";
import Hilde, { type HildeState } from "@/components/ui/Hilde";

const STATES: HildeState[] = ["idle", "thinking", "found", "confused", "wave"];

const STATE_LABELS: Record<HildeState, string> = {
  idle: "Idle",
  thinking: "Denkt nach",
  found: "Hat's gefunden",
  confused: "Verwirrt",
  wave: "Winkt",
};

function Hero({
  size,
  setSize,
  state,
  setState,
  replayKey,
  replay,
}: {
  size: number;
  setSize: (n: number) => void;
  state: HildeState;
  setState: (s: HildeState) => void;
  replayKey: number;
  replay: () => void;
}) {
  return (
    <section
      className="grid grid-cols-1 md:grid-cols-2 gap-6 md:gap-8 items-center rounded-2xl border border-border p-6 md:p-12 mb-8"
      style={{ background: "linear-gradient(135deg, #F5E6CC 0%, #EBEDF0 100%)" }}
    >
      <div className="flex justify-center order-1 md:order-none">
        <Hilde key={replayKey} size={size} state={state} />
      </div>

      <div>
        <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-muted mb-2">
          Spielwiese · Hilde
        </div>
        <h1 className="m-0 text-4xl md:text-5xl font-bold text-kb leading-none tracking-tight">
          Hilde
        </h1>
        <div className="text-base md:text-lg text-muted mt-1.5 font-medium">
          Belesen, ein bisschen schrullig
        </div>

        <div className="mt-7">
          <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-muted mb-2.5">
            State
          </div>
          <div className="flex flex-wrap gap-2">
            {STATES.map((s) => (
              <button
                key={s}
                onClick={() => setState(s)}
                className={`px-3.5 py-2 rounded-full text-xs font-semibold border transition-all ${
                  state === s
                    ? "bg-kb text-white border-kb"
                    : "bg-white text-foreground-soft border-border hover:border-kb"
                }`}
              >
                {STATE_LABELS[s]}
              </button>
            ))}
          </div>
        </div>

        <div className="mt-6">
          <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-muted mb-2.5">
            Größe · {size}px
          </div>
          <input
            type="range"
            min={32}
            max={320}
            step={4}
            value={size}
            onChange={(e) => setSize(+e.target.value)}
            className="w-full"
            style={{ accentColor: "var(--kb)" }}
          />
          <div className="flex justify-between mt-1.5 text-[11px] text-muted">
            <span>32 (Avatar)</span>
            <span className="hidden sm:inline">120 (Standard)</span>
            <span>320 (Hero)</span>
          </div>
        </div>

        <div className="mt-6">
          <button
            onClick={replay}
            className="btn-primary inline-flex items-center gap-2 px-5 py-2.5 rounded-full text-xs font-semibold"
          >
            <span className="text-[11px]">▶</span>
            Animationen neu abspielen
          </button>
        </div>
      </div>
    </section>
  );
}

function StatesGrid() {
  return (
    <section className="mb-8">
      <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-muted mb-3.5">
        Alle Stimmungen nebeneinander
      </div>
      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-3">
        {STATES.map((s) => (
          <div
            key={s}
            className="flex flex-col items-center gap-3 py-6 px-3 bg-surface rounded-xl border border-border"
          >
            <Hilde size={120} state={s} />
            <div className="text-[11px] font-semibold text-foreground-soft uppercase tracking-[0.1em] text-center">
              {STATE_LABELS[s]}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

function ChatMockup() {
  const [bubbleState, setBubbleState] = useState<HildeState>("thinking");

  return (
    <section className="mb-8">
      <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-muted mb-3.5">
        Im Chat-Kontext (so würde sie im KI-Assistenten erscheinen)
      </div>

      <div className="bg-white rounded-xl border border-border p-4 sm:p-6 flex flex-col gap-4">
        <div className="flex justify-end">
          <div
            className="bg-kb text-white px-3.5 py-2.5 rounded-[20px] text-sm leading-relaxed max-w-[85%] sm:max-w-[70%]"
            style={{ borderBottomRightRadius: 6 }}
          >
            Kannst du mir die Kapitel 3 und 4 aus dem Skript zusammenfassen?
          </div>
        </div>

        <div className="flex items-start gap-2.5">
          <div className="shrink-0 mt-0.5">
            <Hilde size={36} state={bubbleState} />
          </div>
          <div
            className="bg-surface text-foreground-soft px-3.5 py-2.5 rounded-[20px] text-sm leading-relaxed max-w-[85%] sm:max-w-[70%] border border-border"
            style={{ borderBottomLeftRadius: 6 }}
          >
            {bubbleState === "thinking" && "Einen Moment, ich gehe das Skript durch…"}
            {bubbleState === "found" &&
              "Klar! Hier die Kernpunkte aus Kapitel 3 und 4: Markov-Ketten beschreiben Übergänge zwischen Zuständen, wobei die Wahrscheinlichkeit nur vom aktuellen Zustand abhängt…"}
            {bubbleState === "idle" && "Bereit. Was möchtest du wissen?"}
            {bubbleState === "confused" &&
              "Hm, das Kapitel finde ich im Skript nicht eindeutig. Meintest du Kapitel 3 oder die Übungsaufgaben dazu?"}
            {bubbleState === "wave" && "Hallo! Schön, dass du da bist. Womit kann ich helfen?"}
          </div>
        </div>

        <div className="flex flex-wrap gap-2 pt-3 border-t border-border items-center">
          <span className="text-[11px] text-muted mr-1">Bubble-State:</span>
          {STATES.map((s) => (
            <button
              key={s}
              onClick={() => setBubbleState(s)}
              className={`px-2.5 py-1 rounded-full text-[11px] font-semibold border transition-colors ${
                bubbleState === s
                  ? "bg-kb text-white border-kb"
                  : "bg-white text-muted border-border hover:border-kb"
              }`}
            >
              {STATE_LABELS[s]}
            </button>
          ))}
        </div>
      </div>
    </section>
  );
}

function SizesRow() {
  const sizes = [24, 32, 48, 64, 96, 140];
  return (
    <section className="mb-8">
      <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-muted mb-3.5">
        Größen-Test (Idle)
      </div>
      <div className="flex gap-4 sm:gap-6 items-end justify-center flex-wrap p-4 sm:p-6 bg-surface rounded-xl border border-border">
        {sizes.map((sz) => (
          <div key={sz} className="flex flex-col items-center gap-2">
            <Hilde size={sz} state="idle" />
            <div className="text-[11px] text-muted font-semibold">{sz}px</div>
          </div>
        ))}
      </div>
    </section>
  );
}

export default function HildeTab() {
  const [size, setSize] = useState(280);
  const [state, setState] = useState<HildeState>("wave");
  const [replayKey, setReplayKey] = useState(0);
  const replay = () => setReplayKey((k) => k + 1);

  return (
    <div>
      <Hero
        size={size}
        setSize={setSize}
        state={state}
        setState={setState}
        replayKey={replayKey}
        replay={replay}
      />
      <StatesGrid />
      <ChatMockup />
      <SizesRow />
    </div>
  );
}

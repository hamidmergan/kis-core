"use client";

import { useState, type ComponentType } from "react";
import { useTranslations } from "next-intl";
import type { MascotState } from "@/components/ui/Mascot";

type MascotComponent = ComponentType<{ size?: number; state?: MascotState; className?: string }>;

const STATES: MascotState[] = ["idle", "thinking", "found", "confused", "wave"];

const STATE_KEYS: Record<MascotState, string> = {
  idle: "stateIdle",
  thinking: "stateThinking",
  found: "stateFound",
  confused: "stateConfused",
  wave: "stateWave",
};

function Hero({
  ns,
  Mascot,
  size,
  setSize,
  state,
  setState,
  replayKey,
  replay,
}: {
  ns: string;
  Mascot: MascotComponent;
  size: number;
  setSize: (n: number) => void;
  state: MascotState;
  setState: (s: MascotState) => void;
  replayKey: number;
  replay: () => void;
}) {
  const t = useTranslations(ns);
  return (
    <section
      className="grid grid-cols-1 md:grid-cols-2 gap-6 md:gap-8 items-center rounded-2xl border border-border p-6 md:p-12 mb-8"
      style={{ background: "linear-gradient(135deg, #F5E6CC 0%, #EBEDF0 100%)" }}
    >
      <div className="flex justify-center order-1 md:order-none">
        <Mascot key={replayKey} size={size} state={state} />
      </div>

      <div>
        <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-muted mb-2">
          {t("categoryLabel")}
        </div>
        <h1 className="m-0 text-4xl md:text-5xl font-bold text-kb leading-none tracking-tight">
          {t("title")}
        </h1>
        <div className="text-base md:text-lg text-muted mt-1.5 font-medium">
          {t("subtitle")}
        </div>

        <div className="mt-7">
          <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-muted mb-2.5">
            {t("stateHeading")}
          </div>
          <div className="flex flex-wrap md:flex-nowrap gap-2">
            {STATES.map((s) => (
              <button
                key={s}
                onClick={() => setState(s)}
                className={`px-3.5 py-2 rounded-full text-xs font-semibold border transition-all whitespace-nowrap ${
                  state === s
                    ? "bg-kb text-white border-kb"
                    : "bg-background text-foreground-soft border-border hover:border-kb"
                }`}
              >
                {t(STATE_KEYS[s])}
              </button>
            ))}
          </div>
        </div>

        <div className="mt-6">
          <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-muted mb-2.5">
            {t("sizeHeading", { size })}
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
            <span>{t("sizeAvatar")}</span>
            <span className="hidden sm:inline">{t("sizeStandard")}</span>
            <span>{t("sizeHero")}</span>
          </div>
        </div>

        <div className="mt-6">
          <button
            onClick={replay}
            className="btn-primary inline-flex items-center gap-2 px-5 py-2.5 rounded-full text-xs font-semibold"
          >
            <span className="text-[11px]">▶</span>
            {t("replay")}
          </button>
        </div>
      </div>
    </section>
  );
}

function StatesGrid({ ns, Mascot }: { ns: string; Mascot: MascotComponent }) {
  const t = useTranslations(ns);
  return (
    <section className="mb-8">
      <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-muted mb-3.5">
        {t("allMoodsHeading")}
      </div>
      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-3">
        {STATES.map((s) => (
          <div
            key={s}
            className="flex flex-col items-center gap-3 py-6 px-3 bg-surface rounded-xl border border-border"
          >
            <Mascot size={120} state={s} />
            <div className="text-[11px] font-semibold text-foreground-soft tracking-[0.1em] text-center">
              {t(STATE_KEYS[s]).replace(/ß/g, "ẞ").toUpperCase()}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

function ChatMockup({ ns, Mascot }: { ns: string; Mascot: MascotComponent }) {
  const t = useTranslations(ns);
  const [bubbleState, setBubbleState] = useState<MascotState>("thinking");

  const bubbleTextKey: Record<MascotState, string> = {
    thinking: "chatThinking",
    found: "chatFound",
    idle: "chatIdle",
    confused: "chatConfused",
    wave: "chatWave",
  };

  return (
    <section className="mb-8">
      <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-muted mb-3.5">
        {t("chatHeading")}
      </div>

      <div className="bg-background rounded-xl border border-border p-4 sm:p-6 flex flex-col gap-4">
        <div className="flex justify-end">
          <div
            className="bg-kb text-white px-3.5 py-2.5 rounded-[20px] text-sm leading-relaxed max-w-[85%] sm:max-w-[70%]"
            style={{ borderBottomRightRadius: 6 }}
          >
            {t("chatUserMessage")}
          </div>
        </div>

        <div className="flex items-start gap-2.5">
          <div className="shrink-0 mt-0.5">
            <Mascot size={36} state={bubbleState} />
          </div>
          <div
            className="bg-surface text-foreground-soft px-3.5 py-2.5 rounded-[20px] text-sm leading-relaxed max-w-[85%] sm:max-w-[70%] border border-border"
            style={{ borderBottomLeftRadius: 6 }}
          >
            {t(bubbleTextKey[bubbleState])}
          </div>
        </div>

        <div className="flex flex-wrap gap-2 pt-3 border-t border-border items-center">
          <span className="text-[11px] text-muted mr-1">{t("bubbleStateLabel")}</span>
          {STATES.map((s) => (
            <button
              key={s}
              onClick={() => setBubbleState(s)}
              className={`px-2.5 py-1 rounded-full text-[11px] font-semibold border transition-colors ${
                bubbleState === s
                  ? "bg-kb text-white border-kb"
                  : "bg-background text-muted border-border hover:border-kb"
              }`}
            >
              {t(STATE_KEYS[s])}
            </button>
          ))}
        </div>
      </div>
    </section>
  );
}

function SizesRow({ ns, Mascot }: { ns: string; Mascot: MascotComponent }) {
  const t = useTranslations(ns);
  const sizes = [24, 32, 48, 64, 96, 140];
  return (
    <section className="mb-8">
      <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-muted mb-3.5">
        {t("sizesHeading")}
      </div>
      <div className="flex gap-4 sm:gap-6 items-end justify-center flex-wrap p-4 sm:p-6 bg-surface rounded-xl border border-border">
        {sizes.map((sz) => (
          <div key={sz} className="flex flex-col items-center gap-2">
            <Mascot size={sz} state="idle" />
            <div className="text-[11px] text-muted font-semibold">{sz}px</div>
          </div>
        ))}
      </div>
    </section>
  );
}

/** Interactive playground for a single mascot character. */
export default function MascotShowcase({
  Component,
  namespace,
}: {
  Component: MascotComponent;
  namespace: string;
}) {
  const [size, setSize] = useState(280);
  const [state, setState] = useState<MascotState>("wave");
  const [replayKey, setReplayKey] = useState(0);
  const replay = () => setReplayKey((k) => k + 1);

  return (
    <div>
      <Hero
        ns={namespace}
        Mascot={Component}
        size={size}
        setSize={setSize}
        state={state}
        setState={setState}
        replayKey={replayKey}
        replay={replay}
      />
      <StatesGrid ns={namespace} Mascot={Component} />
      <ChatMockup ns={namespace} Mascot={Component} />
      <SizesRow ns={namespace} Mascot={Component} />
    </div>
  );
}

"use client";

import { useEffect, useState, type ReactNode } from "react";
import { useTranslations } from "next-intl";
import { ArrowsLeftRight, Check, Copy } from "@phosphor-icons/react";
import IconButton from "@/components/ui/IconButton";
import Spinner from "@/components/ui/Spinner";
import StatusMark from "@/components/ui/StatusMark";
import { copyTextFromPromise } from "@/lib/clipboard";
import LanguageSelect from "./LanguageSelect";
import MicButton from "./MicButton";
import SpeakerName from "./SpeakerName";
import { CARD_TEXTS, LANG_CODES, type CardTexts } from "../_cardTexts";
import type { Floor, Notice } from "../_hooks/useConversation";
import { localeOf, type LangCode, type Side, type Turn } from "../_types";

interface Props {
  turns: Turn[];
  recording: Side | null;
  /** The microphone is on but nothing is coming in. */
  quiet: boolean;
  /** The recording is running into its time limit. */
  endingSoon: boolean;
  floor: Floor | null;
  ended: boolean;
  notice: Notice | null;
  langs: Record<Side, LangCode>;
  names: Record<Side, string>;
  /** Languages and seats can only change while nothing was said. */
  allowSetup: boolean;
  onLanguage: (side: Side, code: LangCode) => void;
  onRename: (side: Side, name: string) => void;
  onSwap: () => void;
  onMic: (side: Side) => void;
  onBegin: (side: Side) => void;
  onType: (side: Side, text: string) => void;
  onTranslate: (side: Side) => void;
  formatTime: (at: number) => string;
}

/** What the field of one card holds: the sentence of this side, the translation of the other, or nothing yet. */
type Stage =
  | { kind: "own"; turn: Turn }
  | { kind: "other"; turn: Turn }
  | { kind: "blank" };

/** Each person keeps a colour of their own, cool on the left and warm on the right. */
const CARD_TINT: Record<Side, string> = { left: "var(--badge-blue-bg)", right: "var(--badge-amber-bg)" };
const NAME_COLOR: Record<Side, string> = { left: "var(--badge-blue-fg)", right: "var(--badge-amber-fg)" };
const FIELD = "w-full flex-1 min-h-[16rem] rounded-md border-2 px-2.5 py-1.5 text-base leading-relaxed text-foreground placeholder:text-muted-soft focus:outline-none transition-colors resize-y";
const EDITABLE = "border-border bg-background hover:border-kb focus:border-kb";
const READ_ONLY = "border-border-soft bg-background/60 cursor-default";
const CARET = <span aria-hidden="true" className="ml-0.5 animate-pulse text-kb">▍</span>;
/** The history shows this many of the newest sentences, the rest waits behind a button. */
const HISTORY_LIMIT = 20;

/** One card per person, each written in its own language, the whole conversation as a list below. */
export default function ConversationView(p: Props) {
  const t = useTranslations("tools.interpreter");
  const [copied, setCopied] = useState<Side | null>(null);
  const last = p.turns.length ? p.turns[p.turns.length - 1] : null;
  // The newest sentence sits right under the cards, older ones follow below.
  const history = p.turns.filter((turn) => turn.original.trim()).reverse();
  const [showAll, setShowAll] = useState(false);
  useEffect(() => {
    if (p.turns.length === 0) setShowAll(false);
  }, [p.turns.length]);
  const hidden = showAll ? 0 : Math.max(0, history.length - HISTORY_LIMIT);
  const shown = hidden ? history.slice(0, HISTORY_LIMIT) : history;

  const stage = (side: Side): Stage => {
    const turn = (id: string | null) => (id ? p.turns.find((item) => item.id === id) : undefined);
    if (p.floor) {
      const held = turn(p.floor.id);
      if (!held) return { kind: "blank" };
      return p.floor.side === side ? { kind: "own", turn: held } : { kind: "other", turn: held };
    }
    if (!last) return { kind: "blank" };
    return last.side === side ? { kind: "own", turn: last } : { kind: "other", turn: last };
  };

  const head = (side: Side, x: CardTexts) => (
    <div className="flex items-center justify-between gap-3 min-w-0">
      <LanguageSelect
        id={`interpreter-lang-${side}`}
        value={p.langs[side]}
        onChange={(code) => p.onLanguage(side, code)}
        languages={LANG_CODES.map((code) => ({ id: code, label: x.languages[code] }))}
        label={x.languageLabel}
        disabled={!p.allowSetup}
      />
      <SpeakerName name={p.names[side]} onRename={(name) => p.onRename(side, name)} renameLabel={x.rename} errorText={x.renameError} />
    </div>
  );

  const mark = (side: Side, st: Stage, x: CardTexts): ReactNode => {
    if (p.recording === side) return <StatusMark tone="error" pulse className="text-xs">{x.listening}</StatusMark>;
    if (st.kind === "other" && (st.turn.status === "transcribing" || st.turn.status === "translating")) {
      return <StatusMark tone="brand" pulse className="text-xs">{x.live}</StatusMark>;
    }
    // The translation card names whose sentence it carries, the own card already says so in its head.
    if (st.kind === "other") return <span className="text-xs text-muted-soft">{p.names[st.turn.side]}</span>;
    return null;
  };

  const status = (side: Side, st: Stage, x: CardTexts): ReactNode => {
    if (p.recording === side) {
      if (p.endingSoon) return <span className="text-warn">{x.endingSoon}</span>;
      if (p.quiet) return <span className="text-warn">{x.noSound}</span>;
      return x.listeningHint;
    }
    if (p.recording) return x.waiting(p.names[p.recording]);
    if (p.ended) return x.ended;
    if (p.notice && p.notice.side === side) {
      return p.notice.kind === "mic" ? x.micDenied : p.notice.kind === "stt" ? x.sttFailed : x.nothingHeard;
    }
    if (st.kind === "own") {
      if (st.turn.status === "transcribing") return <Spinner size="sm" label={x.transcribing} />;
      if (st.turn.status === "translating") return x.translating;
      if (st.turn.status === "pending") return x.pressTranslate;
      return st.turn.original.trim() ? x.editHint : x.idle;
    }
    if (st.kind === "other" && st.turn.status === "failed") return <span className="text-error">{x.failed}</span>;
    return x.idle;
  };

  const copy = (side: Side, text: string) => {
    copyTextFromPromise(Promise.resolve(text));
    setCopied(side);
    setTimeout(() => setCopied(null), 1500);
  };

  const field = (side: Side, st: Stage, x: CardTexts): ReactNode => {
    if (p.recording === side && st.kind === "own") {
      return (
        <div className={`${FIELD} border-transparent whitespace-pre-wrap break-words`} aria-live="polite">
          {st.turn.original || <span className="text-muted-soft">…</span>}
          {CARET}
        </div>
      );
    }
    if (st.kind === "other") {
      return (
        <textarea
          id={`interpreter-field-${side}`}
          value={st.turn.translation}
          readOnly
          onFocus={() => { if (!p.ended) p.onBegin(side); }}
          placeholder={st.turn.original.trim() ? "…" : x.translationHere}
          aria-label={x.translationAria}
          aria-live="polite"
          spellCheck={false}
          className={`${FIELD} ${READ_ONLY}`}
        />
      );
    }
    const writable = !p.ended && (st.kind === "blank" || st.turn.status !== "transcribing");
    return (
      <textarea
        id={`interpreter-field-${side}`}
        value={st.kind === "own" ? st.turn.original : ""}
        onChange={(e) => p.onType(side, e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            p.onTranslate(side);
          }
        }}
        onBlur={() => p.onTranslate(side)}
        readOnly={!writable}
        placeholder={x.empty}
        aria-label={x.fieldAria}
        spellCheck={false}
        className={`${FIELD} ${writable ? EDITABLE : READ_ONLY}`}
      />
    );
  };

  // Whoever is speaking, typing or spoke last carries the accent border.
  const active: Side | null = p.recording ?? p.floor?.side ?? last?.side ?? null;

  const card = (side: Side) => {
    const x = CARD_TEXTS[p.langs[side]];
    const st = stage(side);
    const translation = st.kind === "other" ? st.turn.translation : "";
    return (
      <div
        key={side}
        lang={localeOf(p.langs[side])}
        data-side={side}
        className={`h-full flex flex-col rounded-xl border-2 min-w-0 transition-colors ${active === side ? "border-kb" : "border-border-soft"}`}
        style={{ backgroundColor: CARD_TINT[side] }}
      >
        <div className="px-3 pt-3 pb-2" style={{ borderBottom: "1px solid var(--border-soft)" }}>{head(side, x)}</div>
        <div className="px-3 py-3 flex flex-col gap-1.5 flex-1">
          {mark(side, st, x)}
          {field(side, st, x)}
          <div className="flex items-center gap-3 min-h-[3rem]">
            <MicButton recording={p.recording === side} disabled={p.ended} onClick={() => p.onMic(side)} startLabel={x.speak} stopLabel={x.stop} />
            {st.kind === "own" && st.turn.status === "pending" && (
              <button type="button" onClick={() => p.onTranslate(side)} className="px-3 py-1.5 text-sm btn-primary rounded-md">
                {x.translate}
              </button>
            )}
            <p className="text-xs text-muted flex-1 min-w-0">{status(side, st, x)}</p>
            {st.kind === "other" && (
              <IconButton
                onClick={() => copy(side, translation)}
                disabled={!translation}
                aria-label={copied === side ? x.copied : x.copy}
                title={copied === side ? x.copied : x.copy}
                className="disabled:opacity-40"
              >
                {copied === side ? <Check size={14} weight="bold" className="text-success" /> : <Copy size={14} weight="bold" />}
              </IconButton>
            )}
          </div>
        </div>
      </div>
    );
  };

  return (
    <>
      <div className="grid grid-cols-1 md:grid-cols-[1fr_auto_1fr] gap-4 md:gap-3 items-stretch">
        {card("left")}
        <div className="flex justify-center items-center">
          <IconButton onClick={p.onSwap} disabled={!p.allowSetup} aria-label={t("languages.swap")} title={t("languages.swap")} className="disabled:opacity-40">
            <ArrowsLeftRight size={14} weight="bold" />
          </IconButton>
        </div>
        {card("right")}
      </div>

      {history.length > 0 && (
        <section className="mt-6">
          <h2 className="text-sm font-semibold text-foreground-soft mb-3">{t("history.title")}</h2>
          <ol className="space-y-3">
            {shown.map((turn) => {
              const right = turn.side === "right";
              return (
                <li key={turn.id} className={`flex ${right ? "justify-end" : ""}`}>
                  <div className="max-w-[72%] min-w-0">
                    <p className={`mb-1 flex gap-2 text-xs text-muted-soft ${right ? "justify-end" : ""}`}>
                      {right && <span>{p.formatTime(turn.at)}</span>}
                      <span className="font-semibold" style={{ color: NAME_COLOR[turn.side] }}>{p.names[turn.side]}</span>
                      {!right && <span>{p.formatTime(turn.at)}</span>}
                    </p>
                    <div className={`rounded-2xl px-4 py-2.5 text-sm ${right ? "rounded-br-sm" : "rounded-bl-sm"}`} style={{ backgroundColor: CARD_TINT[turn.side] }}>
                      <p className="font-semibold text-foreground whitespace-pre-wrap break-words">{turn.original}</p>
                      <p className="text-foreground-soft whitespace-pre-wrap break-words">{turn.translation || "…"}</p>
                    </div>
                  </div>
                </li>
              );
            })}
          </ol>
          {hidden > 0 && (
            <p className="mt-3 text-center">
              <button type="button" onClick={() => setShowAll(true)} className="text-xs text-muted hover:text-kb">
                {t("history.showOlder", { count: hidden })}
              </button>
            </p>
          )}
        </section>
      )}
    </>
  );
}

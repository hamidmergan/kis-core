import React, { useMemo, useRef, useState } from "react";
import { CaretRight } from "@phosphor-icons/react";
import { useTranslations } from "next-intl";
import type { ExerciseSet } from "../../_types";
import { checkGap, type ClozeVerdict } from "./_cloze";
import { SetSourceLegend } from "./SetSourceLegend";
import { SubviewHeader, type BreadcrumbItem } from "../layout/SubviewHeader";

const PLACEHOLDER_RE = /\{\{(\d+)\}\}/g;

const VERDICT_STYLE: Record<ClozeVerdict, { fg: string; bg: string }> = {
  correct: { fg: "#1a8a5c", bg: "rgba(26,138,92,0.08)" },
  close: { fg: "#b07d1a", bg: "rgba(176,125,26,0.10)" },
  wrong: { fg: "#d4453a", bg: "rgba(212,69,58,0.07)" },
};

/** One set, one text, one button, checked in the browser. */
export function ClozeExerciseView({
  exerciseSet, onBack, onAnswer, onSourceClick, onFinish, breadcrumbs,
}: {
  exerciseSet: ExerciseSet;
  onBack: () => void;
  onAnswer: (itemId: number, correct: boolean, newRun: boolean) => void;
  onSourceClick?: (filename: string, page: number, startTime?: number) => void;
  onFinish?: (correct: number, total: number) => void;
  breadcrumbs?: BreadcrumbItem[];
}) {
  const t = useTranslations("workspace.detail.languageTraining");

  // One text is exactly one exercise, instruction and example hang off it.
  const item = exerciseSet.items?.[0] ?? null;
  const gaps = useMemo(() => item?.extras?.gaps ?? [], [item]);
  const instruction = item?.extras?.instruction ?? "";
  const example = item?.extras?.example ?? null;

  // The text split into pieces and gaps.
  const parts = useMemo(() => {
    const out: { text?: string; gap?: number }[] = [];
    const src = item?.front ?? "";
    let last = 0;
    for (const m of src.matchAll(PLACEHOLDER_RE)) {
      if (m.index! > last) out.push({ text: src.slice(last, m.index) });
      out.push({ gap: Number(m[1]) - 1 });
      last = m.index! + m[0].length;
    }
    if (last < src.length) out.push({ text: src.slice(last) });
    return out;
  }, [item]);

  // All fields equally wide, otherwise the width reveals the answer length.
  const maxSolutionLen = useMemo(
    () => Math.max(6, ...gaps.map((g) => g.solution.length)),
    [gaps],
  );

  // The chips are shuffled once per exercise so the order reveals nothing.
  const chips = useMemo(() => {
    const list = gaps.map((g, i) => ({ base: g.base, key: i }));
    for (let i = list.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [list[i], list[j]] = [list[j], list[i]];
    }
    return list;
    // The exercise id is the stable key, not the object.
  }, [item?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  const [drafts, setDrafts] = useState<Record<number, string>>({});
  const [struck, setStruck] = useState<Record<number, boolean>>({});
  // Collapsed, the example is help on demand.
  const [showExample, setShowExample] = useState(false);
  const [verdicts, setVerdicts] = useState<ClozeVerdict[] | null>(null);
  // Whether it was checked really locks every field.
  const checked = verdicts !== null;
  // One mount of the view is one round.
  const runGemeldetRef = useRef(false);

  const gefuellt = Object.values(drafts).some((v) => v.trim());
  const correctCount = verdicts?.filter((v) => v === "correct").length ?? 0;

  function check() {
    // Without the length guard an exercise without gaps would pass as mastered.
    if (!item || checked || gaps.length === 0) return;
    const urteile = gaps.map((g, i) => checkGap(drafts[i] ?? "", g.solution));
    setVerdicts(urteile);
    // The text is ONE exercise, mastered when every gap is right.
    const neuerDurchgang = !runGemeldetRef.current;
    runGemeldetRef.current = true;
    onAnswer(item.id, urteile.every((u) => u === "correct"), neuerDurchgang);
  }

  if (!item) return null;

  return (
    <div className="flex flex-col h-full">
      {/* Kein toolKey: der Satztitel ist der Name des Uebungssatzes und steht
          schlicht in Schriftfarbe, so wie bei Grammatik und Karteikarten. Die
          Farbmarke traegt nur das Werkzeug im Pfad davor. */}
      <SubviewHeader
        title={exerciseSet.title}
        category="language_training"
        onBack={onBack}
        breadcrumbs={breadcrumbs}
      />
      <div className="flex-1 overflow-y-auto p-4 flex flex-col gap-4">
        {instruction && (
          <p className="text-xs" style={{ color: "var(--muted)" }}>{instruction}</p>
        )}
        {example?.gapped && example?.solved && (
          <div>
            <button type="button" onClick={() => setShowExample((v) => !v)}
              aria-expanded={showExample}
              className="inline-flex items-center gap-1 text-xs font-medium transition-colors hover:text-kb"
              style={{ color: "var(--muted)" }}>
              <CaretRight size={10} weight="bold"
                className={`transition-transform ${showExample ? "rotate-90" : ""}`} />
              {t("cloze.example")}
            </button>
            {showExample && (
              <div className="mt-1.5 rounded-xl px-3 py-2" style={{ backgroundColor: "var(--surface-dim)" }}>
                {/* Gleiche Groesse wie der Lueckentext selbst: alles, was der Lernende
                    LIEST, liest sich auf einer Stufe. Klein bleiben nur die Bedienteile. */}
                <p className="text-sm leading-relaxed" style={{ color: "var(--foreground-soft)" }}>{example.gapped}</p>
                {/* Der Pfeil traegt die Richtung ohne Wort und braucht keine
                    Uebersetzung. Fuer einen Screenreader nur Zierde. */}
                <p className="text-sm leading-relaxed flex gap-1.5" style={{ color: "var(--foreground-soft)" }}>
                  <span aria-hidden="true" className="shrink-0" style={{ color: "var(--kb)" }}>→</span>
                  <span>{example.solved}</span>
                </p>
              </div>
            )}
          </div>
        )}

        {/* Der Fliesstext ist modell-verfasst und wird als reine React-Textknoten
            gerendert, nie ueber dangerouslySetInnerHTML: das Modell schreibt hier
            frei formulierten Text und keine vertrauenswuerdige Auszeichnung. */}
        <p className="text-sm leading-8">
          {parts.map((p, i) => p.text !== undefined ? (
            <span key={i}>{p.text}</span>
          ) : (
            <GapInput
              key={i}
              value={drafts[p.gap!] ?? ""}
              onChange={(v) => setDrafts((d) => ({ ...d, [p.gap!]: v }))}
              verdict={verdicts?.[p.gap!] ?? null}
              locked={checked}
              solution={gaps[p.gap!]?.solution ?? ""}
              width={maxSolutionLen}
            />
          ))}
        </p>

        <div className="flex flex-wrap gap-1.5">
          {chips.map((c) => (
            <button
              key={c.key}
              type="button"
              onClick={() => setStruck((s) => ({ ...s, [c.key]: !s[c.key] }))}
              className="px-2.5 py-1 rounded-full text-2xs font-medium border-2 transition-colors"
              // Neutral grey, a chip is material and not a judgement.
              style={{
                backgroundColor: "var(--surface-dim)",
                color: "var(--foreground)",
                borderColor: "var(--border)",
                textDecoration: struck[c.key] ? "line-through" : "none",
                opacity: struck[c.key] ? 0.5 : 1,
              }}
            >
              {c.base}
            </button>
          ))}
        </div>

        {/* Signatur aus dem Bestand: sources und ein onSourceClick, das NUR den
            Dateinamen bekommt. Die Seite steht am Chip und nicht an der Legende. */}
        <SetSourceLegend
          sources={exerciseSet.sources}
          onSourceClick={(filename) => onSourceClick?.(filename, item.page_number ?? 1)}
        />
      </div>

      <div className="px-4 py-3 flex items-center gap-3"
        style={{ borderTop: "1px solid var(--border)" }}>
        {!checked ? (
          <button type="button" onClick={check} disabled={!gefuellt}
            className="btn-fill-accent px-5 py-2 rounded-full text-xs font-semibold disabled:opacity-50">
            {t("cloze.check")}
          </button>
        ) : (
          <>
            <span className="text-xs font-semibold">
              {t("cloze.score", { correct: correctCount, total: gaps.length })}
            </span>
            <button type="button" onClick={() => onFinish?.(correctCount, gaps.length)}
              className="btn-fill-accent ml-auto px-5 py-2 rounded-full text-xs font-semibold">
              {t("common.done")}
            </button>
          </>
        )}
      </div>
    </div>
  );
}

function GapInput({ value, onChange, verdict, locked, solution, width }: {
  value: string;
  onChange: (v: string) => void;
  verdict: ClozeVerdict | null;
  locked: boolean;
  solution: string;
  width: number;
}) {
  const style = verdict ? VERDICT_STYLE[verdict] : null;
  return (
    <span className="inline-flex items-baseline gap-1">
      <input
        type="text"
        value={value}
        disabled={locked}
        onChange={(e) => onChange(e.target.value)}
        className="px-1.5 py-0.5 rounded text-sm text-center border-b-2 bg-transparent outline-none"
        style={{
          borderColor: style ? style.fg : "var(--border)",
          backgroundColor: style ? style.bg : "transparent",
          color: style ? style.fg : "var(--foreground)",
          width: `${width + 2}ch`,
        }}
      />
      {verdict && verdict !== "correct" && (
        <span className="text-2xs font-semibold" style={{ color: VERDICT_STYLE.correct.fg }}>
          {solution}
        </span>
      )}
    </span>
  );
}

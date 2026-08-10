import React, { useMemo, useState } from "react";
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

/** Ein Satz, ein Text, ein Knopf.
 *
 * Der Text kommt mit Platzhaltern und wird hier an ihnen zerlegt. Zwischen die
 * Stücke kommen Eingabefelder. Unter dem Text stehen die Grundformen als Chips,
 * ein Klick streicht einen durch und ein zweiter hebt den Strich auf. Das ist
 * eine Merkhilfe und hat auf die Auswertung keinen Einfluss.
 *
 * Geprüft wird im Browser. Die Lösungen kommen mit dem Satz mit, das ist Absicht.
 */
export function ClozeExerciseView({
  exerciseSet, onBack, onAnswer, onSourceClick, onFinish, breadcrumbs,
}: {
  exerciseSet: ExerciseSet;
  onBack: () => void;
  onAnswer: (itemId: number, correct: boolean) => void;
  onSourceClick?: (filename: string, page: number, startTime?: number) => void;
  onFinish?: (correct: number, total: number) => void;
  breadcrumbs?: BreadcrumbItem[];
}) {
  const t = useTranslations("workspace.detail.languageTraining");

  // Ein Set ist genau EINE Aufgabe (siehe run_cloze_set im Backend), deshalb reicht
  // das erste Element. Anweisung und Beispiel haengen an DIESER Aufgabe und nicht
  // am Set (exerciseSet.instruction/pattern_* gehoeren der Grammatik-Uebung, der
  // Vorrat traegt nur Aufgaben mit, kein Set-Feld).
  const item = exerciseSet.items?.[0] ?? null;
  const gaps = useMemo(() => item?.extras?.gaps ?? [], [item]);
  const instruction = item?.extras?.instruction ?? "";
  const example = item?.extras?.example ?? null;

  // Der Text in Stücke und Lücken zerlegt. Ein Stück ist Text, eine Lücke ist die
  // (0-indizierte) Nummer eines Platzhalters, ueber die gaps[] angesprochen wird.
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

  // Alle Eingabefelder gleich breit, nach der LAENGSTEN Loesung im Satz. Die Breite
  // aus der eigenen Loesung einer Luecke zu nehmen wuerde die Antwortlaenge schon
  // verraten, bevor ueberhaupt etwas eingetippt ist.
  const maxSolutionLen = useMemo(
    () => Math.max(6, ...gaps.map((g) => g.solution.length)),
    [gaps],
  );

  // Die Chips einmal gemischt, damit ihre Reihenfolge die Lösung nicht verrät. Die
  // Ansicht öffnet sich mit der Listenzeile, BEVOR die Aufgabe nachgeladen ist: beim
  // ersten Rendern ist item noch null und gaps damit leer. Ein useState-Initialisierer
  // liefe genau einmal beim Mounten und fröre diesen leeren Stand für immer ein, die
  // Chip-Reihe bliebe leer, obwohl der Text und die Eingabefelder (über ihre eigenen
  // useMemo) richtig nachziehen. useMemo über die Aufgaben-Id läuft dagegen erneut,
  // sobald die echte Aufgabe eintrifft, danach aber nicht mehr bei jedem Neuzeichnen
  // (Tippen, Prüfen, Chip-Klick ändern die Id nicht). Genau einmal PRO SATZ, nicht
  // einmal pro Mount.
  const chips = useMemo(() => {
    const list = gaps.map((g, i) => ({ base: g.base, key: i }));
    for (let i = list.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [list[i], list[j]] = [list[j], list[i]];
    }
    return list;
    // gaps absichtlich nicht in den deps: seine Identität hängt an item und würde bei
    // jedem Objekt-Neuaufbau ohne echte Datenänderung mitmischen, item.id ist der
    // stabile Schlüssel dafür, ob wirklich eine ANDERE Aufgabe vorliegt.
  }, [item?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  const [drafts, setDrafts] = useState<Record<number, string>>({});
  const [struck, setStruck] = useState<Record<number, boolean>>({});
  const [verdicts, setVerdicts] = useState<ClozeVerdict[] | null>(null);
  // Ob geprueft wurde, unabhaengig davon, ob jede Luecke ein eigenes Urteil bekam.
  // Sperrt so wirklich JEDES Feld (Vorgabe), auch ein Platzhalter ohne passenden
  // gaps-Eintrag, statt an einem einzelnen Urteil festzumachen.
  const checked = verdicts !== null;

  const gefuellt = Object.values(drafts).some((v) => v.trim());
  const correctCount = verdicts?.filter((v) => v === "correct").length ?? 0;

  function check() {
    if (!item || checked) return;
    const urteile = gaps.map((g, i) => checkGap(drafts[i] ?? "", g.solution));
    setVerdicts(urteile);
    // Der Satz ist EINE Aufgabe. Sie gilt als gekonnt, wenn jede Lücke sitzt.
    onAnswer(item.id, urteile.every((u) => u === "correct"));
  }

  if (!item) return null;

  return (
    <div className="flex flex-col h-full">
      <SubviewHeader
        title={exerciseSet.title}
        toolKey="Cloze"
        category="language_training"
        onBack={onBack}
        breadcrumbs={breadcrumbs}
      />
      <div className="flex-1 overflow-y-auto p-4 flex flex-col gap-4">
        {instruction && (
          <p className="text-xs" style={{ color: "var(--muted)" }}>{instruction}</p>
        )}
        {example?.gapped && example?.solved && (
          <div className="rounded-xl px-3 py-2 text-xs"
            style={{ backgroundColor: "var(--surface-dim)" }}>
            <div>{example.gapped}</div>
            <div style={{ color: "var(--kb)" }}>→ {example.solved}</div>
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
              style={{
                backgroundColor: "var(--badge-rose-bg)",
                color: "var(--badge-rose-fg)",
                borderColor: "transparent",
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
        size={width}
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

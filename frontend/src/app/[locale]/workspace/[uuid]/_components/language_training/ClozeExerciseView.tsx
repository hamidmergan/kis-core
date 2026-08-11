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
  onAnswer: (itemId: number, correct: boolean, newRun: boolean) => void;
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
  // Eingeklappt: das Beispiel ist Hilfe auf Abruf und nicht Teil der Aufgabe.
  // Genauso haelt es die Grammatik-Uebung mit ihrem Musterpaar.
  const [showExample, setShowExample] = useState(false);
  const [verdicts, setVerdicts] = useState<ClozeVerdict[] | null>(null);
  // Ob geprueft wurde, unabhaengig davon, ob jede Luecke ein eigenes Urteil bekam.
  // Sperrt so wirklich JEDES Feld (Vorgabe), auch ein Platzhalter ohne passenden
  // gaps-Eintrag, statt an einem einzelnen Urteil festzumachen.
  const checked = verdicts !== null;
  // Ein Aufbau der Ansicht ist ein Durchgang.
  const runGemeldetRef = useRef(false);

  const gefuellt = Object.values(drafts).some((v) => v.trim());
  const correctCount = verdicts?.filter((v) => v === "correct").length ?? 0;

  function check() {
    // Ohne die Laengen-Wache waere [] hier ein gueltiges Urteil: [].every(...) ist
    // in JavaScript immer true, und eine Aufgabe ohne Luecken (kaputte extras.gaps)
    // ginge damit als gekonnt durch, obwohl nie etwas geprueft wurde.
    if (!item || checked || gaps.length === 0) return;
    const urteile = gaps.map((g, i) => checkGap(drafts[i] ?? "", g.solution));
    setVerdicts(urteile);
    // Der Satz ist EINE Aufgabe. Sie gilt als gekonnt, wenn jede Lücke sitzt.
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
              // Neutrales Grau aus der hauseigenen Skala und nicht die Rose-Farbe der
              // Kachel. Ein Chip ist Material zum Einsetzen und keine Wertung, eine
              // Farbe daran wuerde eine Bedeutung behaupten, die es nicht gibt. Die
              // beiden Werte sind fuer hell und dunkel getrennt hinterlegt.
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

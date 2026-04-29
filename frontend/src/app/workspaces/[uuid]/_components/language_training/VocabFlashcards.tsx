import { useEffect, useState } from "react";
import { ArrowCounterClockwise, Check, WarningCircle, XIcon } from "@phosphor-icons/react";
import type { GlossaryEntry } from "../../_types";
import { _chunkLabel, _md } from "../../_utils";
import { SubviewHeader, type BreadcrumbItem } from "../layout/SubviewHeader";

export function VocabFlashcards({
  entries, onBack, breadcrumbs,
}: {
  entries: GlossaryEntry[];
  onBack: () => void;
  breadcrumbs?: BreadcrumbItem[];
}) {
  const [index, setIndex] = useState(0);
  const [flipped, setFlipped] = useState(false);
  const [results, setResults] = useState<{ glossary_entry_id: number; correct: boolean }[]>([]);
  const [finished, setFinished] = useState(false);

  useEffect(() => { setFlipped(false); }, [index]);

  const card = entries[index];
  const total = entries.length;
  const correctCount = results.filter((r) => r.correct).length;

  function handleAnswer(correct: boolean) {
    const newResults = [...results, { glossary_entry_id: card.id, correct }];
    setResults(newResults);
    if (index + 1 < total) {
      setIndex(index + 1);
    } else {
      setFinished(true);
    }
  }

  const wrongEntries = finished
    ? results.filter((r) => !r.correct).map((r) => entries.find((e) => e.id === r.glossary_entry_id)).filter(Boolean) as GlossaryEntry[]
    : [];

  if (finished) {
    return (
      <div className="flex flex-col h-full">
        <SubviewHeader title="Karteikarten" toolKey="Flashcards" onBack={onBack} breadcrumbs={breadcrumbs} category="language_training" />
        <div className="flex-1 overflow-y-auto">
          <div className="mx-auto w-full px-4 pt-8 pb-6 flex flex-col items-center gap-5" style={{ maxWidth: 560 }}>
            <div className="text-center">
              <p className="text-lg font-bold" style={{ color: "var(--text)" }}>Ergebnis</p>
              <p className="text-3xl font-bold mt-2" style={{ color: "var(--accent)" }}>
                {correctCount} / {total}
              </p>
              <p className="text-xs mt-1" style={{ color: "var(--muted)" }}>
                {Math.round((correctCount / total) * 100)}% gewusst
              </p>
            </div>

            {/* Progress bar */}
            <div className="w-full rounded-full h-2.5 overflow-hidden" style={{ backgroundColor: "var(--border)" }}>
              <div
                className="h-full rounded-full transition-all"
                style={{ width: `${(correctCount / total) * 100}%`, backgroundColor: "#22c55e" }}
              />
            </div>

            {wrongEntries.length > 0 && (
              <div className="w-full rounded-xl p-4" style={{ backgroundColor: "rgba(239,68,68,0.06)", border: "1px solid rgba(239,68,68,0.15)" }}>
                <p className="text-xs font-semibold mb-2" style={{ color: "#B91C1C" }}>
                  <WarningCircle size={13} weight="bold" className="inline mr-1" style={{ verticalAlign: "-2px" }} />
                  Nochmal lernen:
                </p>
                <div className="flex flex-col gap-1.5">
                  {wrongEntries.map((e) => (
                    <div key={e.id} className="flex items-center gap-2 text-xs" style={{ color: "var(--text)" }}>
                      <span className="font-semibold">{e.term_de}</span>
                      <span style={{ color: "var(--muted)" }}>—</span>
                      <span style={{ color: "var(--muted)" }}>{e.term_en}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <div className="flex gap-2 w-full">
              {wrongEntries.length > 0 && (
                <button
                  type="button"
                  onClick={() => { setIndex(0); setResults([]); setFinished(false); }}
                  className="flex-1 py-2.5 rounded-xl text-xs font-semibold transition-opacity hover:opacity-90"
                  style={{ backgroundColor: "rgba(239,68,68,0.1)", color: "#B91C1C", border: "1px solid rgba(239,68,68,0.2)" }}
                >
                  <ArrowCounterClockwise size={13} weight="bold" className="inline mr-1" style={{ verticalAlign: "-1px" }} />
                  Alle nochmal
                </button>
              )}
              <button
                type="button"
                onClick={onBack}
                className="flex-1 py-2.5 rounded-xl text-xs font-semibold transition-opacity hover:opacity-90"
                style={{ backgroundColor: "var(--border)", color: "var(--text)" }}
              >
                Zurück
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      <SubviewHeader title="Karteikarten" toolKey="Flashcards" onBack={onBack} breadcrumbs={breadcrumbs} category="language_training" />
      <div className="flex-1 overflow-y-auto p-4">
        <div className="mx-auto mt-4 sm:mt-6 w-full flex flex-col gap-3" style={{ maxWidth: 560 }}>
          {/* Card */}
          {card && (
            <>
            <div className="text-center text-xs font-semibold" style={{ color: "var(--muted)" }}>
              {index + 1} / {total}
            </div>
            <div className="rounded-2xl overflow-hidden" style={{ backgroundColor: flipped ? "rgba(var(--accent-rgb),0.04)" : "var(--surface)", boxShadow: "0 4px 20px rgba(0,40,60,0.08)" }}>
              {/* Progress bar as top border */}
              <div className="w-full" style={{ height: 3, backgroundColor: "var(--border)" }}>
                <div className="h-full transition-all duration-500 rounded-r-full" style={{ width: `${((index + 1) / total) * 100}%`, backgroundColor: "var(--kb)" }} />
              </div>
              <div
                className="w-full p-6 text-center"
                style={{
                  minHeight: 180,
                  backgroundColor: "transparent",
                  display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 8,
                }}
              >
                {!flipped ? (
                  <span className="text-sm font-semibold" style={{ color: "var(--text)" }}>{card.term_de}</span>
                ) : (
                  <>
                    <span className="text-xs font-semibold uppercase tracking-wider" style={{ color: "var(--accent)" }}>
                      {card.term_en}
                    </span>
                    <span className="text-sm leading-relaxed font-semibold" style={{ color: "var(--text)" }}
                      dangerouslySetInnerHTML={{ __html: _md(card.definition) }} />
                    {card.page_number && (
                      <span className="text-xs mt-1" style={{ color: "var(--muted)" }}>{card.filename ? _chunkLabel(card.filename, card.page_number!) : `S. ${card.page_number}`}</span>
                    )}
                  </>
                )}
              </div>
            </div>
          </>
          )}

          {/* Toggle + Answer buttons */}
          {!flipped ? (
            <button type="button" onClick={() => setFlipped(true)}
              className="btn-soft-accent w-full py-2.5 rounded-xl text-xs font-semibold transition-all">
              Antwort zeigen
            </button>
          ) : (
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => handleAnswer(false)}
                className="flex-1 py-2.5 rounded-xl text-xs font-semibold transition-all hover:outline-2 hover:outline-[#B91C1C]"
                style={{ backgroundColor: "rgba(239,68,68,0.1)", color: "#B91C1C", border: "1px solid rgba(239,68,68,0.2)" }}
              >
                <XIcon size={13} weight="bold" className="inline mr-1" style={{ verticalAlign: "-1px" }} />
                Nochmal
              </button>
              <button type="button" onClick={() => setFlipped(false)}
                className="btn-soft-accent py-2.5 px-4 rounded-xl text-xs font-semibold transition-all">
                Frage zeigen
              </button>
              <button
                type="button"
                onClick={() => handleAnswer(true)}
                className="flex-1 py-2.5 rounded-xl text-xs font-semibold transition-opacity hover:opacity-90"
                style={{ backgroundColor: "rgba(34,197,94,0.1)", color: "#166534", border: "1px solid rgba(34,197,94,0.2)" }}
              >
                <Check size={13} weight="bold" className="inline mr-1" style={{ verticalAlign: "-1px" }} />
                Gewusst
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}


"use client";

/** The one active evaluation, filled out question by question. */

import { useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import Header from "@/components/layout/Header";
import Mascot from "@/components/ui/Mascot";
import Spinner from "@/components/ui/Spinner";
import { useMascotPref } from "@/hooks/useMascotPref";
import { useRouter } from "@/i18n/navigation";
import { hatAnfang } from "./intro";
import { zuSenden } from "./antworten";
import { springtWeiter } from "./sprung";

type Frage = { id: string; type: "scale" | "text"; text: string; scale_low?: string; scale_high?: string };

type AktiveEvaluation = {
  active: boolean;
  title?: string;
  intro_text?: string;
  intro_link_label?: string;
  intro_link_url?: string;
  outro_text?: string;
  outro_link_label?: string;
  outro_link_url?: string;
  questions?: Frage[];
  already_responded?: boolean;
};

type Antworten = Record<string, string | number>;

type Stufe = "loading" | "unavailable" | "intro" | "questions" | "outro";

export default function EvaluationPage() {
  const t = useTranslations("evaluationFlow");
  const router = useRouter();
  const { variant: figur } = useMascotPref();
  const [daten, setDaten] = useState<AktiveEvaluation | null>(null);
  const [stufe, setStufe] = useState<Stufe>("loading");
  const [index, setIndex] = useState(0);
  const [antworten, setAntworten] = useState<Antworten>({});
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const sprungTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    fetch("/api/evaluation/active", { credentials: "include" })
      .then((r) => (r.ok ? r.json() : null))
      .then((d: AktiveEvaluation | null) => {
        setDaten(d);
        // Answering again is a deliberate choice, reachable through the settings menu,
        // so an earlier answer never blocks the flow here.
        if (!d?.active) {
          setStufe("unavailable");
          return;
        }
        setStufe(hatAnfang(d) ? "intro" : "questions");
      })
      .catch(() => setStufe("unavailable"));
  }, []);

  async function submit() {
    if (!daten?.questions) return;
    const abgabe = zuSenden(daten.questions, antworten);
    // Nothing answered is not a mistake, so it ends on the closing screen instead of an error.
    if (abgabe.length === 0) {
      setStufe("outro");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const r = await fetch("/api/evaluation/submit", {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ answers: abgabe }),
      });
      if (!r.ok) {
        setError(t("submitError"));
        return;
      }
      setStufe("outro");
    } catch {
      setError(t("submitError"));
    } finally {
      setSubmitting(false);
    }
  }

  // A pending jump must never outlive the question it was started on.
  useEffect(() => () => {
    if (sprungTimer.current) clearTimeout(sprungTimer.current);
  }, [index]);

  function waehle(id: string, wert: number) {
    setAntworten({ ...antworten, [id]: wert });
    if (!springtWeiter(daten?.questions, index)) return;
    if (sprungTimer.current) clearTimeout(sprungTimer.current);
    // A short pause so the picked circle is visible before the next question opens.
    sprungTimer.current = setTimeout(() => setIndex((i) => i + 1), 250);
  }

  function weiter() {
    if (!daten?.questions) return;
    if (index + 1 >= daten.questions.length) {
      submit();
    } else {
      setIndex(index + 1);
    }
  }

  // An empty label falls back to the wording that was there before labels per question.
  function rand(frage: Frage, seite: "scale_low" | "scale_high"): string {
    return frage[seite]?.trim() || t(seite === "scale_low" ? "scaleLow" : "scaleHigh");
  }

  function zurueck() {
    if (index === 0) return;
    setError(null);
    setIndex(index - 1);
  }

  return (
    <>
      <Header />
      <div className="flex items-center justify-center min-h-[70vh] px-4 py-12">
        <div className="w-full max-w-md">
          {stufe === "loading" && (
            <div className="flex justify-center py-12"><Spinner /></div>
          )}

          {stufe === "unavailable" && (
            <div className="bg-background rounded-xl shadow-sm border border-border-soft p-8 text-center space-y-3">
              <p className="text-sm" style={{ color: "var(--foreground-soft)" }}>
                {t("notAvailable")}
              </p>
              <button
                type="button"
                onClick={() => router.push("/")}
                className="px-4 py-2 text-sm btn-primary rounded-md transition-colors"
              >
                {t("backToHome")}
              </button>
            </div>
          )}

          {stufe === "intro" && daten && (
            <div className="bg-background rounded-xl shadow-sm border border-border-soft p-8 flex flex-col items-center text-center gap-4">
              <Mascot variant={figur} size={80} state="confused" />
              <h1 className="text-lg font-semibold">{daten.title}</h1>
              {daten.intro_text && (
                <p className="text-sm" style={{ color: "var(--foreground-soft)" }}>{daten.intro_text}</p>
              )}
              {daten.intro_link_url && (
                <a
                  href={daten.intro_link_url}
                  target="_blank"
                  rel="noreferrer"
                  className="text-sm underline"
                  style={{ color: "var(--kb)" }}
                >
                  {daten.intro_link_label || daten.intro_link_url}
                </a>
              )}
              <button
                type="button"
                onClick={() => setStufe("questions")}
                className="w-full px-4 py-2 text-sm btn-primary rounded-md transition-colors"
              >
                {t("start")}
              </button>
            </div>
          )}

          {stufe === "questions" && daten?.questions && (
            <div className="bg-background rounded-xl shadow-sm border border-border-soft px-8 py-10 flex flex-col gap-6">
              <div className="h-1 w-full rounded-full overflow-hidden" style={{ backgroundColor: "var(--surface-dim)" }}>
                <div
                  className="h-full rounded-full bg-kb transition-all"
                  style={{ width: `${((index + 1) / daten.questions.length) * 100}%` }}
                />
              </div>
              <p className="text-xs uppercase tracking-wide text-muted">
                {t("progress", { current: index + 1, total: daten.questions.length })}
              </p>
              <div className="flex justify-center py-4">
                <Mascot variant={figur} size={80} state="confused" />
              </div>
              <p className="text-sm font-medium">{daten.questions[index].text}</p>

              {daten.questions[index].type === "scale" ? (
                <div className="flex justify-center py-2">
                  {/* Labels sit beside the scale where there is room and drop under its ends when there is not. */}
                  <div className="inline-flex flex-col items-center sm:flex-row sm:gap-3">
                    <span className="hidden sm:block text-xs text-muted">{rand(daten.questions[index], "scale_low")}</span>
                    <div className="flex gap-3 sm:gap-2">
                      {[1, 2, 3, 4, 5].map((n) => {
                        const gewaehlt = antworten[daten.questions![index].id] === n;
                        return (
                          <button
                            key={n}
                            type="button"
                            onClick={() => waehle(daten.questions![index].id, n)}
                            className={
                              "w-12 h-12 rounded-full border-2 text-base flex items-center justify-center transition-colors " +
                              (gewaehlt
                                ? "border-kb bg-kb text-white"
                                : "border-border text-foreground-soft hover:border-kb")
                            }
                          >
                            {n}
                          </button>
                        );
                      })}
                    </div>
                    <span className="hidden sm:block text-xs text-muted">{rand(daten.questions[index], "scale_high")}</span>
                    <div className="flex justify-between w-full mt-2 text-xs text-muted sm:hidden">
                      <span>{rand(daten.questions[index], "scale_low")}</span>
                      <span>{rand(daten.questions[index], "scale_high")}</span>
                    </div>
                  </div>
                </div>
              ) : (
                <textarea
                  value={(antworten[daten.questions[index].id] as string) || ""}
                  onChange={(e) => setAntworten({ ...antworten, [daten.questions![index].id]: e.target.value })}
                  rows={3}
                  className="w-full text-sm border border-border rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-kb resize-none"
                />
              )}

              {error && <p className="text-sm text-error">{error}</p>}

              <div className="flex items-center justify-between">
                {index > 0 ? (
                  <button
                    type="button"
                    onClick={zurueck}
                    disabled={submitting}
                    className="px-4 py-2 text-sm rounded-md border-2 border-border text-foreground-soft hover:border-kb transition-colors disabled:opacity-60"
                  >
                    {t("back")}
                  </button>
                ) : <span />}
                <button
                  type="button"
                  onClick={weiter}
                  disabled={submitting}
                  className="px-4 py-2 text-sm btn-primary rounded-md transition-colors disabled:opacity-60"
                >
                  {index + 1 >= daten.questions.length
                    ? (submitting ? t("submitting") : t("submit"))
                    : t("next")}
                </button>
              </div>
            </div>
          )}

          {stufe === "outro" && daten && (
            <div className="bg-background rounded-xl shadow-sm border border-border-soft p-8 flex flex-col items-center text-center gap-4">
              <Mascot variant={figur} size={120} state="wave" />
              <h1 className="text-lg font-semibold">{t("thanksTitle")}</h1>
              {daten.outro_text && (
                <p className="text-sm" style={{ color: "var(--foreground-soft)" }}>{daten.outro_text}</p>
              )}
              {daten.outro_link_url && (
                <a
                  href={daten.outro_link_url}
                  target="_blank"
                  rel="noreferrer"
                  className="text-sm underline"
                  style={{ color: "var(--kb)" }}
                >
                  {daten.outro_link_label || daten.outro_link_url}
                </a>
              )}
              <button
                type="button"
                onClick={() => router.push("/")}
                className="w-full px-4 py-2 text-sm btn-primary rounded-md transition-colors"
              >
                {t("backToHome")}
              </button>
            </div>
          )}
        </div>
      </div>
    </>
  );
}

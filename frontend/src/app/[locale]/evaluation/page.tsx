"use client";

/** The one active evaluation, filled out question by question. */

import { useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { Check } from "@phosphor-icons/react";
import Header from "@/components/layout/Header";
import Mascot from "@/components/ui/Mascot";
import Spinner from "@/components/ui/Spinner";
import { useMascotPref } from "@/hooks/useMascotPref";
import { useRouter } from "@/i18n/navigation";
import { zuSenden } from "./antworten";
import { naechsterSichtbarerIndex, istSichtbar } from "./sichtbarkeit";
import { springtWeiter } from "./sprung";

type ShowIf = { question_id: string; in: string[] };
type Frage = {
  id: string;
  type: "choice" | "multi" | "text";
  text: string;
  options?: string[];
  skippable?: boolean;
  show_if?: ShowIf;
};

type AktiveEvaluation = {
  active: boolean;
  title?: string;
  intro_text?: string;
  intro_link_label?: string;
  intro_link_url?: string;
  outro_text?: string;
  outro_link_label?: string;
  outro_link_url?: string;
  contact_email?: string;
  questions?: Frage[];
  already_responded?: boolean;
};

type Antworten = Record<string, string | string[]>;

type Stufe = "loading" | "unavailable" | "intro" | "questions" | "outro";

const NICHT_GETESTET = "not_tested";

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
        // The anonymity notice always has something to say, so the intro step always opens first.
        setStufe("intro");
      })
      .catch(() => setStufe("unavailable"));
  }, []);

  async function submit(quelle: Antworten = antworten) {
    if (!daten?.questions) return;
    const abgabe = zuSenden(daten.questions, quelle);
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

  function gehtWeiterZu(aktualisiert: Antworten) {
    if (!daten?.questions) return;
    const next = naechsterSichtbarerIndex(daten.questions, aktualisiert, index + 1, 1);
    if (next >= daten.questions.length) {
      submit(aktualisiert);
    } else {
      setIndex(next);
    }
  }

  function waehle(id: string, wert: string) {
    const aktualisiert = { ...antworten, [id]: wert };
    setAntworten(aktualisiert);
    if (!springtWeiter(daten?.questions, index)) return;
    if (sprungTimer.current) clearTimeout(sprungTimer.current);
    // A short pause so the picked row is visible before the next question opens.
    sprungTimer.current = setTimeout(() => gehtWeiterZu(aktualisiert), 250);
  }

  function toggleMulti(id: string, option: string) {
    const bisher = Array.isArray(antworten[id]) ? (antworten[id] as string[]) : [];
    const neu = bisher.includes(option) ? bisher.filter((o) => o !== option) : [...bisher, option];
    setAntworten({ ...antworten, [id]: neu });
  }

  function nichtGetestet(id: string) {
    const aktualisiert = { ...antworten, [id]: NICHT_GETESTET };
    setAntworten(aktualisiert);
    gehtWeiterZu(aktualisiert);
  }

  function weiter() {
    if (!daten?.questions) return;
    const next = naechsterSichtbarerIndex(daten.questions, antworten, index + 1, 1);
    if (next >= daten.questions.length) {
      submit();
    } else {
      setIndex(next);
    }
  }

  function zurueck() {
    if (!daten?.questions) return;
    const prev = naechsterSichtbarerIndex(daten.questions, antworten, index - 1, -1);
    if (prev < 0) return;
    setError(null);
    setIndex(prev);
  }

  const frage = daten?.questions?.[index];
  const sichtbareFragen = daten?.questions?.filter((f) => istSichtbar(f, antworten)) ?? [];
  const position = frage ? sichtbareFragen.findIndex((f) => f.id === frage.id) + 1 : 0;

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
                onClick={() => router.push("/services")}
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
              <p className="text-sm font-medium">{t("anonymousNotice")}</p>
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

          {stufe === "questions" && daten?.questions && frage && (
            <div className="bg-background rounded-xl shadow-sm border border-border-soft px-8 py-10 flex flex-col gap-6">
              <div className="h-1 w-full rounded-full overflow-hidden" style={{ backgroundColor: "var(--surface-dim)" }}>
                <div
                  className="h-full rounded-full bg-kb transition-all"
                  style={{ width: `${(position / sichtbareFragen.length) * 100}%` }}
                />
              </div>
              <p className="text-xs uppercase tracking-wide text-muted">
                {t("progress", { current: position })}
              </p>
              <div className="flex justify-center py-4">
                <Mascot variant={figur} size={80} state="confused" />
              </div>
              <p className="text-sm font-medium">{frage.text}</p>

              {frage.type === "text" ? (
                <textarea
                  value={(antworten[frage.id] as string) || ""}
                  onChange={(e) => setAntworten({ ...antworten, [frage.id]: e.target.value })}
                  rows={3}
                  maxLength={2000}
                  className="w-full text-sm border border-border rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-kb resize-none"
                />
              ) : (
                <div className="flex flex-col gap-2">
                  {frage.options?.map((option) => {
                    const istMulti = frage.type === "multi";
                    const ausgewaehlt = istMulti
                      ? Array.isArray(antworten[frage.id]) && (antworten[frage.id] as string[]).includes(option)
                      : antworten[frage.id] === option;
                    return (
                      <button
                        key={option}
                        type="button"
                        onClick={() => (istMulti ? toggleMulti(frage.id, option) : waehle(frage.id, option))}
                        className={
                          "w-full flex items-center gap-3 text-left px-4 py-2.5 text-sm rounded-md border-2 transition-colors " +
                          (ausgewaehlt ? "border-kb" : "border-border text-foreground-soft hover:border-kb")
                        }
                      >
                        <span
                          className={
                            "flex-shrink-0 w-5 h-5 flex items-center justify-center border-2 transition-colors " +
                            (istMulti ? "rounded-md" : "rounded-full") +
                            " " +
                            (ausgewaehlt ? "border-kb bg-kb" : "border-border")
                          }
                          style={{ color: "#fff" }}
                        >
                          {ausgewaehlt && (istMulti ? <Check size={11} weight="bold" /> : <span className="w-2 h-2 rounded-full bg-white" />)}
                        </span>
                        {option}
                      </button>
                    );
                  })}
                </div>
              )}

              {frage.skippable && (
                <button
                  type="button"
                  onClick={() => nichtGetestet(frage.id)}
                  className="self-start text-xs underline text-muted"
                >
                  {t("notTested")}
                </button>
              )}

              {error && <p className="text-sm text-error">{error}</p>}

              <div className="flex items-center justify-between">
                {position > 1 ? (
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
                  {position >= sichtbareFragen.length
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
              {daten.contact_email && (
                <p className="text-sm" style={{ color: "var(--foreground-soft)" }}>
                  {t("contactPrompt")}{" "}
                  <a href={`mailto:${daten.contact_email}`} className="underline" style={{ color: "var(--kb)" }}>
                    {daten.contact_email}
                  </a>
                </p>
              )}
              <button
                type="button"
                onClick={() => router.push("/services")}
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

"use client";

import { useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { GraduationCap, X } from "@phosphor-icons/react";
import Mascot from "@/components/ui/Mascot";
import { backdropClose, newBackdropPress } from "@/components/ui/backdropClose";
import { useMascotPref } from "@/hooks/useMascotPref";
import { useLanguageDiagnosis } from "../../_hooks/useLanguageDiagnosis";
import { DiagnosisResultScreen } from "./DiagnosisResultScreen";
import { type ChatTurn } from "./_diagnosis_types";

interface Props {
  userId: number | null;
  onComplete: () => void;
  onAbort: () => void;
  hideHeader?: boolean;
}

/** The assessment as a short chat, method and language come from the admin area. */
export function LanguageDiagnosisPanel({
  userId,
  onComplete,
  onAbort,
  hideHeader,
}: Props) {
  const t = useTranslations("workspace.detail.languageTraining.diagnosis");
  const tChat = useTranslations("workspace.detail.chat");
  const [confirmAbort, setConfirmAbort] = useState(false);
  const press = useRef(newBackdropPress()).current;
  const { variant } = useMascotPref();

  const { turns, status, result, errorMessage, send, retry, abort, questionCount, answerMaxChars } =
    useLanguageDiagnosis(userId);

  // One question per model turn, capped because of the final turn.
  const askedCount = Math.min(
    turns.filter((turn) => turn.role === "assistant").length,
    questionCount,
  );

  const scrollRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [turns, status]);

  // The introduction is frame and stays in the interface language.
  const visibleTurns: ChatTurn[] = [{ role: "assistant", content: t("intro") }, ...turns];

  // One bubble per turn, a skipped question gets a label.
  const bubbles: { role: ChatTurn["role"]; text: string }[] = visibleTurns.map((turn) => ({
    role: turn.role,
    text: turn.role === "user" && !turn.content.trim() ? t("skipped") : turn.content,
  }));

  // The current question is the last model turn, the answer key stays on the server.
  const current =
    status === "answering" && turns.length > 0 && turns[turns.length - 1].role === "assistant"
      ? turns[turns.length - 1]
      : undefined;
  const options = current?.options;
  const multi = current?.multi ?? false;
  // A free-text question gets a real text area instead of the chat line.
  const isFreeText = !!current && !(options && options.length > 0);
  // A gap gets a single-line field, decided by the answer length.
  const isShort = current?.short ?? false;

  // Selection and draft are cleared on every new question.
  const [picked, setPicked] = useState<string[]>([]);
  const [draft, setDraft] = useState("");
  useEffect(() => {
    setPicked([]);
    setDraft("");
  }, [turns.length]);

  const togglePick = (value: string) =>
    setPicked((prev) =>
      prev.includes(value) ? prev.filter((v) => v !== value) : [...prev, value],
    );

  // Skipping is always possible, in every answer block.
  const skipButton = (
    <button
      type="button"
      onClick={() => send("")}
      className="self-start text-sm px-3 py-1.5 rounded-lg transition-colors hover:underline"
      style={{ color: "var(--muted)" }}
    >
      {t("skip")}
    </button>
  );

  // The face sits on the newest block, not on the last bubble.
  let mascotIndex = bubbles.map((bubble) => bubble.role).lastIndexOf("assistant");
  while (mascotIndex > 0 && bubbles[mascotIndex - 1].role === "assistant") mascotIndex--;

  return (
    <div className="flex flex-col h-full">
      {!hideHeader && (
        <div
          className="flex items-center justify-between px-4 py-3 border-b"
          style={{ borderColor: "var(--border)" }}
        >
          <div className="flex items-center gap-2">
            <GraduationCap weight="bold" size={20} style={{ color: "var(--kb)" }} />
            <span className="font-semibold" style={{ color: "var(--foreground)" }}>
              {t("title")}
            </span>
            {status !== "done" && askedCount > 0 && (
              <span className="text-sm" style={{ color: "var(--muted)" }}>
                {t("progress", { current: askedCount, total: questionCount })}
              </span>
            )}
          </div>
          <button
            onClick={() => setConfirmAbort(true)}
            className="w-7 h-7 inline-flex items-center justify-center rounded-full btn-icon transition-colors"
            style={{ backgroundColor: "var(--surface-dim)" }}
            aria-label={t("abort")}
          >
            <X weight="bold" size={16} />
          </button>
        </div>
      )}

      {status === "done" && result ? (
        <div className="flex-1 overflow-y-auto">
          <DiagnosisResultScreen result={result} onContinue={onComplete} />
        </div>
      ) : (
        <>
          <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-4">
            <div className="max-w-2xl mx-auto w-full flex flex-col gap-3">
              {bubbles.map((bubble, i) => (
                <div
                  key={i}
                  className={`flex flex-col gap-1.5 ${
                    bubble.role === "user" ? "items-end" : "items-start"
                  }`}
                >
                  {bubble.role === "assistant" && i === mascotIndex && (
                    <div className="flex items-center gap-2 mb-0.5">
                      <Mascot
                        variant={variant}
                        size={80}
                        state={status === "loading" ? "thinking" : "idle"}
                      />
                      <span className="text-base font-medium">
                        {variant === "hilde" ? tChat("hildeName") : tChat("francisName")}
                      </span>
                    </div>
                  )}
                  <div
                    className="px-4 py-2 rounded-2xl text-base leading-snug break-words max-w-[96%] w-fit"
                    style={
                      bubble.role === "user"
                        ? {
                            backgroundColor: "var(--kb)",
                            color: "white",
                            borderBottomRightRadius: 6,
                            whiteSpace: "pre-wrap",
                            overflowWrap: "break-word",
                          }
                        : {
                            backgroundColor: "var(--surface)",
                            color: "var(--foreground)",
                            border: "1px solid var(--border)",
                            borderTopLeftRadius: 6,
                            whiteSpace: "pre-wrap",
                            overflowWrap: "break-word",
                          }
                    }
                  >
                    {bubble.text}
                  </div>
                </div>
              ))}

              {status === "loading" && (
                <div
                  className="px-4 py-2 rounded-2xl w-fit"
                  style={{
                    backgroundColor: "var(--surface)",
                    border: "1px solid var(--border)",
                    borderTopLeftRadius: 6,
                  }}
                  aria-label={t("loading")}
                >
                  <span className="inline-flex gap-1 align-middle">
                    {[0, 1, 2].map((n) => (
                      <span
                        key={n}
                        className="inline-block w-1.5 h-1.5 rounded-full animate-bounce"
                        style={{ backgroundColor: "var(--muted)", animationDelay: `${n * 0.15}s` }}
                      />
                    ))}
                  </span>
                </div>
              )}

              {status === "error" && (
                <div className="flex flex-col items-start gap-2">
                  <p className="text-sm" style={{ color: "var(--error)" }}>
                    {errorMessage || t("errorGeneric")}
                  </p>
                  <button
                    onClick={retry}
                    className="px-4 py-1.5 rounded-lg text-sm"
                    style={{ backgroundColor: "var(--kb)", color: "var(--on-accent)" }}
                  >
                    {t("retry")}
                  </button>
                </div>
              )}
            </div>
          </div>

          {/* Option questions: the values arrive shuffled and the answer key is
              server-side. Click only, no typing. A single-choice option submits on
              click; multi-choice toggles and submits together. */}
          {options && options.length > 0 && (
            <div className="px-4 pt-3 pb-4">
              <div className="max-w-2xl mx-auto w-full flex flex-col gap-2">
                {options.map((opt, i) => {
                  const active = multi && picked.includes(opt);
                  // The letter is display, the option text goes back.
                  const letter = String.fromCharCode(97 + i);
                  return (
                    <button
                      key={`${opt}-${i}`}
                      type="button"
                      onClick={() => (multi ? togglePick(opt) : send(opt, [opt]))}
                      className={`text-left px-4 py-2.5 rounded-xl text-base border-2 transition-colors ${
                        active
                          ? "border-kb text-white"
                          : "border-border text-foreground hover:border-kb"
                      }`}
                      style={{ backgroundColor: active ? "var(--kb)" : "var(--surface)" }}
                    >
                      <span style={{ color: active ? "white" : "var(--muted)" }}>{letter})</span> {opt}
                    </button>
                  );
                })}
                {multi && (
                  <button
                    type="button"
                    onClick={() => picked.length && send(picked.join(", "), picked)}
                    disabled={picked.length === 0}
                    className="mt-1 self-start px-5 py-2 rounded-xl text-base font-medium disabled:opacity-40"
                    style={{ backgroundColor: "var(--kb)", color: "white" }}
                  >
                    {t("submitAnswer")}
                  </button>
                )}
                {skipButton}
              </div>
            </div>
          )}

          {/* A writing sample gets a real textarea and its own submit button (Cmd/Ctrl+Enter also sends), a gap gets a single-line field where Enter submits: one word only. */}
          {isFreeText && (
            <div className="px-4 pt-3 pb-4">
              <div className="max-w-2xl mx-auto w-full flex flex-col gap-2">
                {isShort ? (
                  <input
                    type="text"
                    value={draft}
                    onChange={(e) => setDraft(e.target.value)}
                    maxLength={answerMaxChars}
                    autoFocus
                    placeholder={t("gapPlaceholder")}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" && draft.trim()) {
                        e.preventDefault();
                        send(draft);
                      }
                    }}
                    className="w-full rounded-xl px-4 py-3 text-base bg-surface text-foreground border-2 border-border transition-colors focus:border-kb focus:outline-none"
                  />
                ) : (
                <textarea
                  value={draft}
                  onChange={(e) => setDraft(e.target.value)}
                  maxLength={answerMaxChars}
                  rows={4}
                  autoFocus
                  placeholder={t("chatPlaceholder")}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && (e.metaKey || e.ctrlKey) && draft.trim()) {
                      e.preventDefault();
                      send(draft);
                    }
                  }}
                  className="w-full rounded-xl px-4 py-3 text-base resize-y bg-surface text-foreground border-2 border-border transition-colors focus:border-kb focus:outline-none"
                />
                )}
                <div className="flex items-center justify-between gap-2">
                  {skipButton}
                  <button
                    type="button"
                    onClick={() => draft.trim() && send(draft)}
                    disabled={!draft.trim()}
                    className="px-5 py-2 rounded-xl text-base font-medium disabled:opacity-40"
                    style={{ backgroundColor: "var(--kb)", color: "white" }}
                  >
                    {t("submitAnswer")}
                  </button>
                </div>
              </div>
            </div>
          )}
        </>
      )}

      {confirmAbort && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
          {...backdropClose(press, () => setConfirmAbort(false))}
        >
          <div
            className="rounded-2xl p-6 max-w-sm w-full mx-4"
            style={{ backgroundColor: "var(--surface)" }}
            onClick={(e) => e.stopPropagation()}
          >
            <p className="font-semibold mb-2" style={{ color: "var(--foreground)" }}>
              {t("abortConfirmTitle")}
            </p>
            <p className="text-sm mb-4" style={{ color: "var(--muted)" }}>
              {t("abortConfirmBody")}
            </p>
            <div className="flex justify-end gap-2">
              <button
                onClick={() => setConfirmAbort(false)}
                className="px-4 py-2 rounded-lg"
                style={{ color: "var(--foreground)" }}
              >
                {t("abortConfirmKeep")}
              </button>
              <button
                onClick={() => {
                  setConfirmAbort(false);
                  // The dialog promises the answers are gone, so the history goes too.
                  abort();
                  onAbort();
                }}
                className="px-4 py-2 rounded-lg"
                style={{ backgroundColor: "var(--error)", color: "var(--on-accent)" }}
              >
                {t("abortConfirmDiscard")}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

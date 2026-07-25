"use client";

import { useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { GraduationCap, X } from "@phosphor-icons/react";
import Mascot from "@/components/ui/Mascot";
import { useMascotPref } from "@/hooks/useMascotPref";
import { useLanguageDiagnosis } from "../../_hooks/useLanguageDiagnosis";
import { ChatInputBar } from "../chat/ChatInputBar";
import { DiagnosisResultScreen } from "./DiagnosisResultScreen";
import { type ChatTurn } from "./_diagnosis_types";

interface Props {
  userId: number | null;
  workspaceUuid: string;
  onComplete: () => void;
  onAbort: () => void;
  hideHeader?: boolean;
}

/**
 * The CEFR diagnosis, run as a short adaptive chat.
 *
 * The questions come from the model, driven by the admin-managed prompt and the
 * workspace's diagnosis language, so nothing about the method is hardcoded here.
 * The mascot follows the user's existing preference; there is no separate switch.
 */
export function LanguageDiagnosisPanel({
  userId,
  workspaceUuid,
  onComplete,
  onAbort,
  hideHeader,
}: Props) {
  const t = useTranslations("workspace.detail.languageTraining.diagnosis");
  const tChat = useTranslations("workspace.detail.chat");
  const [confirmAbort, setConfirmAbort] = useState(false);
  const { enabled: mascotEnabled, variant } = useMascotPref();

  const { turns, status, result, errorMessage, send, retry, abort, questionCount, answerMaxChars } =
    useLanguageDiagnosis(userId, workspaceUuid);

  // Each assistant turn is one question (the reaction rides along on the same
  // turn, so it does not add to the count). Clamped because the forced verdict
  // turn is also an assistant turn but is not an extra question.
  const askedCount = Math.min(
    turns.filter((turn) => turn.role === "assistant").length,
    questionCount,
  );

  const scrollRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [turns, status]);

  // The intro is a real speech bubble, but it never goes to the model: it is
  // interface framing, so it stays in the UI language even when the interview
  // itself runs in another one. The prompt tells the model not to greet again.
  const visibleTurns: ChatTurn[] = [{ role: "assistant", content: t("intro") }, ...turns];

  // One assistant turn carries two things: the reaction to the last answer and
  // the new task. They go into separate bubbles, the way a person would send two
  // short messages instead of one long one.
  const bubbles: { role: ChatTurn["role"]; text: string }[] = visibleTurns.flatMap((turn) =>
    turn.reaction
      ? [
          { role: turn.role, text: turn.reaction },
          { role: turn.role, text: turn.content },
        ]
      : [{ role: turn.role, text: turn.content }],
  );

  // The avatar heads the newest block of assistant bubbles. Anchoring it to the
  // last bubble alone would strand the intro above a nameless bubble, since the
  // opening block is intro + first question.
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
            className="p-1 rounded hover:bg-[var(--surface-dim)]"
            style={{ color: "var(--muted)" }}
            aria-label={t("abort")}
          >
            <X weight="bold" size={18} />
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
                      {mascotEnabled ? (
                        <>
                          <Mascot
                            variant={variant}
                            size={80}
                            state={status === "loading" ? "thinking" : "idle"}
                          />
                          <span className="text-base font-medium">
                            {variant === "hilde" ? tChat("hildeName") : tChat("francisName")}
                          </span>
                        </>
                      ) : (
                        <>
                          <div
                            className="w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold text-white flex-shrink-0"
                            style={{ backgroundColor: "var(--kb)" }}
                          >
                            {tChat("assistantBadge")}
                          </div>
                          <span className="text-base font-medium">{tChat("assistantName")}</span>
                        </>
                      )}
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

          {/* Same composer as the tutor chat, so the diagnosis does not look like
              a different product. No source line here, the diagnosis has none. */}
          <ChatInputBar
            loading={false}
            disabled={status !== "answering"}
            placeholder={t("chatPlaceholder")}
            maxLength={answerMaxChars}
            onSend={send}
          />
        </>
      )}

      {confirmAbort && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
          onClick={() => setConfirmAbort(false)}
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
                  // The dialog promises the answers are gone, so drop the saved
                  // transcript too instead of silently resuming it later.
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

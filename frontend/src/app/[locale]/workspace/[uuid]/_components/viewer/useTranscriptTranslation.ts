import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { genericErrorMessage, parseDetail } from "@/lib/api";
import { readUserData, updateUserData } from "@/lib/browserStore";
import { readPendingTranslation, translationProbeOutcome } from "./_transcript";
import { parseVtt, type Cue } from "./_vtt";

const POLL_TIMEOUT_MS = 5 * 60 * 1000;
const POLL_INTERVAL_MS = 5000;

export const transcriptUrl = (workspaceUuid: string, sourceUuid: string, lang: string) =>
  `/api/ai-assistant/workspaces/${workspaceUuid}/sources/${sourceUuid}/transcript?lang=${lang}`;

/** Drops the note of a started translation, it is over or lost. */
function forgetPendingTranslation(sourceUuid: string) {
  updateUserData((d) => {
    const translations = { ...d.translations };
    delete translations[sourceUuid];
    return { ...d, translations };
  });
}

/** Starts a translation of the transcript and waits for its file to appear. */
export function useTranscriptTranslation({
  workspaceUuid, sourceUuid, onDone,
}: {
  workspaceUuid: string;
  sourceUuid: string;
  // Receives the finished track, the wait is over by then.
  onDone: (lang: string, cues: Cue[]) => void;
}) {
  const t = useTranslations("workspace.detail.viewer");
  const [regen, setRegen] = useState<"idle" | "running" | "error">("idle");
  const [regenError, setRegenError] = useState<string | null>(null);
  // The language a running translation waits for, it exists before its file does.
  const [pendingLang, setPendingLang] = useState<string | null>(null);
  const onDoneRef = useRef(onDone);
  onDoneRef.current = onDone;

  // Reattaches to a running translation job, an old failure belongs to the last source.
  const reattach = useCallback((loaded: Record<string, unknown>) => {
    const note = readUserData().translations?.[sourceUuid];
    const waiting = readPendingTranslation(note ? JSON.stringify(note) : null, Date.now());
    setRegenError(null);
    if (waiting && !loaded[waiting]) {
      setPendingLang(waiting);
      setRegen("running");
    } else {
      setPendingLang(null);
      setRegen("idle");
      forgetPendingTranslation(sourceUuid);
    }
  }, [sourceUuid]);

  // Poll for the chosen VTT to appear after a translation task was dispatched.
  useEffect(() => {
    if (regen !== "running" || !pendingLang) return;
    const waiting = pendingLang;
    const started = Date.now();
    // An answer for the previous source must not land in the next one.
    let cancelled = false;
    const ac = new AbortController();
    const fail = (message: string) => {
      clearInterval(timer);
      forgetPendingTranslation(sourceUuid);
      setPendingLang(null);
      setRegen("error");
      setRegenError(message);
    };
    const timer = setInterval(async () => {
      if (Date.now() - started > POLL_TIMEOUT_MS) {
        fail(t("regenEnTimeout"));
        return;
      }
      try {
        const probe = await fetch(
          `/api/ai-assistant/workspaces/${workspaceUuid}/sources/${sourceUuid}/transcript/exists?lang=${waiting}`,
          { credentials: "include", signal: ac.signal },
        );
        if (cancelled || !probe.ok) return;
        const outcome = translationProbeOutcome(await probe.json());
        if (cancelled || outcome.kind === "wait") return;
        if (outcome.kind === "failed") {
          // The task gave up, so the wait ends now instead of at the timeout.
          fail(t("regenEnErrorTitle", { error: outcome.error || t("regenEnUnknownError") }));
          return;
        }
        const res = await fetch(transcriptUrl(workspaceUuid, sourceUuid, waiting), { credentials: "include", signal: ac.signal });
        if (cancelled || !res.ok) return;
        const parsed = parseVtt(await res.text());
        if (cancelled) return;
        clearInterval(timer);
        forgetPendingTranslation(sourceUuid);
        onDoneRef.current(waiting, parsed);
        setPendingLang(null);
        setRegen("idle");
      } catch {
        /* keep polling */
      }
    }, POLL_INTERVAL_MS);
    return () => { cancelled = true; ac.abort(); clearInterval(timer); };
  }, [regen, workspaceUuid, sourceUuid, pendingLang, t]);

  const start = async (lang: string) => {
    if (regen === "running") return;
    setPendingLang(lang);
    setRegen("running");
    setRegenError(null);
    try {
      const res = await fetch(
        `/api/ai-assistant/workspaces/${workspaceUuid}/sources/${sourceUuid}/regenerate-transcript`,
        {
          method: "POST",
          credentials: "include",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ target_lang: lang }),
        },
      );
      if (!res.ok) {
        const detail = (await res.json().catch(() => null))?.detail;
        throw new Error(parseDetail(detail, genericErrorMessage()));
      }
      updateUserData((d) => ({ ...d, translations: { ...d.translations, [sourceUuid]: { ts: Date.now(), lang } } }));
    } catch (e) {
      setRegen("error");
      setPendingLang(null);
      setRegenError(e instanceof Error ? e.message : t("regenEnUnknownError"));
    }
  };

  return { regen, regenError, pendingLang, reattach, start };
}

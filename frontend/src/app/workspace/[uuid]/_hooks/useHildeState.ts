"use client";

import { useEffect, useRef, useState } from "react";
import type { ChatMessage } from "../_types";
import type { HildeState } from "@/components/ui/Hilde";

export type HildeGlobalState = Extract<HildeState, "idle" | "thinking" | "wave" | "confused">;

interface UseHildeStateArgs {
  messages: ChatMessage[];
  loading: boolean;
  error?: unknown;
}

/**
 * Drives the global Hilde mood and surfaces a found-trigger counter
 * that consumers can latch onto to flash the latest avatar to "found"
 * when the assistant attaches its first source citation.
 */
export function useHildeState({ messages, loading, error }: UseHildeStateArgs): {
  globalState: HildeGlobalState;
  foundTrigger: number;
} {
  const globalState: HildeGlobalState = error
    ? "confused"
    : loading
      ? "thinking"
      : messages.length === 0
        ? "wave"
        : "idle";

  const [foundTrigger, setFoundTrigger] = useState(0);
  const lastIndexRef = useRef(-1);
  const lastCitationCountRef = useRef(0);

  useEffect(() => {
    const lastIdx = messages.length - 1;
    const last = messages[lastIdx];

    if (!last || last.role !== "assistant") {
      lastIndexRef.current = lastIdx;
      lastCitationCountRef.current = 0;
      return;
    }

    const count = last.source_qmap?.length ?? 0;

    if (lastIndexRef.current !== lastIdx) {
      lastIndexRef.current = lastIdx;
      lastCitationCountRef.current = count;
      return;
    }

    if (lastCitationCountRef.current === 0 && count > 0) {
      setFoundTrigger((n) => n + 1);
    }
    lastCitationCountRef.current = count;
  }, [messages]);

  return { globalState, foundTrigger };
}

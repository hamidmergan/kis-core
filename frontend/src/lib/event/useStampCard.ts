"use client";

import { useCallback, useEffect, useState } from "react";
import { eventApi } from "@/lib/event/api";
import { EMPTY_CARD, type Card } from "@/lib/event/types";

export type CodeOutcome = { result: "stamped"; stationId: string } | { result: "wrong" | "locked" };

/** The visitor's card from the server, every change goes through it. */
export function useStampCard() {
  const [card, setCard] = useState<Card>(EMPTY_CARD);
  const [ready, setReady] = useState(false);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let alive = true;
    eventApi
      .card()
      .then((c) => alive && setCard(c))
      .catch(() => alive && setFailed(true))
      .finally(() => alive && setReady(true));
    return () => {
      alive = false;
    };
  }, []);

  const stamp = useCallback(async (stationId: string): Promise<boolean> => {
    try {
      const res = await eventApi.stamp(stationId);
      setCard(res.card);
      return true;
    } catch {
      return false;
    }
  }, []);

  const submitCode = useCallback(async (code: string): Promise<CodeOutcome | null> => {
    try {
      const res = await eventApi.code(code);
      setCard(res.card);
      if (res.result === "stamped" && res.stationId) return { result: "stamped", stationId: res.stationId };
      return { result: res.result === "locked" ? "locked" : "wrong" };
    } catch {
      return null;
    }
  }, []);

  /** Puts the card into the raffle, null on success, otherwise the server's message or an empty string. */
  const enterRaffle = useCallback(async (email: string): Promise<string | null> => {
    try {
      setCard(await eventApi.raffleEnter(email));
      return null;
    } catch (e) {
      return e instanceof Error ? e.message : "";
    }
  }, []);

  return { card, ready, failed, stamp, submitCode, enterRaffle };
}

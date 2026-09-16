"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { translateText, type Glossary } from "../_api";
import { charState, countChars } from "../_limits";
import { createLiveTranslator, type LiveTranslator } from "../_liveTranslator";
import { localeOf, newId, otherSide, type LangCode, type Side, type Turn } from "../_types";
import { useRecorder, type RecorderError } from "./useRecorder";

interface Options {
  langOf: (side: Side) => LangCode;
  providerId: number | null;
  sttProviderId: number | null;
  glossary: Glossary;
  /** Every change of a sentence, for the page that keeps the conversation on the server. */
  onTurn?: (turn: Turn) => void;
}

export type Notice = { side: Side; kind: RecorderError | "empty" };

/** Whose sentence the cards show right now: a side with its sentence, or a side that only took the floor. */
export interface Floor {
  side: Side;
  id: string | null;
}

const byTime = (a: Turn, b: Turn) => a.at - b.at;

/** The conversation: each field holds one sentence, speech is translated while it grows, typed text on Enter. */
export function useConversation(options: Options) {
  const optionsRef = useRef(options);
  optionsRef.current = options;

  const [turns, setTurns] = useState<Turn[]>([]);
  const [recording, setRecording] = useState<Side | null>(null);
  const [floor, setFloorState] = useState<Floor | null>(null);
  const [ended, setEndedState] = useState(false);
  const [notice, setNotice] = useState<Notice | null>(null);
  const [quiet, setQuiet] = useState(false);
  const [endingSoon, setEndingSoon] = useState(false);

  const recorder = useRecorder();
  const turnsRef = useRef<Turn[]>([]);
  const recordingRef = useRef<Side | null>(null);
  const floorRef = useRef<Floor | null>(null);
  const endedRef = useRef(false);
  const live = useRef<LiveTranslator | null>(null);
  const liveFor = useRef<{ id: string; side: Side } | null>(null);
  const lastLive = useRef<{ id: string; text: string; translation: string } | null>(null);
  // Sentences the server already has, an emptied one has to reach it once more.
  const sent = useRef<Set<string>>(new Set());

  const setFloor = useCallback((next: Floor | null) => {
    floorRef.current = next;
    setFloorState(next);
  }, []);

  const setEnded = useCallback((next: boolean) => {
    endedRef.current = next;
    setEndedState(next);
  }, []);

  // --- turns, always through here so the server sees every change ------------------------

  const commit = useCallback((list: Turn[]) => {
    turnsRef.current = list;
    setTurns(list);
  }, []);

  const find = (id: string) => turnsRef.current.find((turn) => turn.id === id);

  const emit = (turn: Turn) => {
    if (!turn.original.trim() && !sent.current.has(turn.id)) return;
    sent.current.add(turn.id);
    optionsRef.current.onTurn?.(turn);
  };

  const addTurn = useCallback((turn: Turn) => {
    commit([...turnsRef.current, turn].sort(byTime));
    emit(turn);
  }, [commit]);

  const patch = useCallback((id: string, changes: Partial<Turn>) => {
    let next: Turn | undefined;
    commit(turnsRef.current.map((turn) => (turn.id === id ? (next = { ...turn, ...changes }) : turn)));
    if (next) emit(next);
  }, [commit]);

  const translateFor = useCallback((text: string, side: Side) => {
    const { langOf, providerId, glossary } = optionsRef.current;
    return translateText(text, langOf(otherSide(side)), providerId, glossary);
  }, []);

  /** The whole sentence once more, for the moment the live translation is behind. */
  const translate = useCallback(async (id: string, text: string, side: Side) => {
    patch(id, { status: "translating" });
    try {
      const translation = await translateFor(text, side);
      if (find(id)?.original.trim() === text) patch(id, { translation, status: "done" });
    } catch {
      if (find(id)?.original.trim() === text) patch(id, { status: "failed" });
    }
  }, [patch, translateFor]);

  // --- the translation that runs while somebody speaks or types ---------------------------

  useEffect(() => {
    live.current = createLiveTranslator(
      async (text) => {
        const target = liveFor.current;
        if (!target) throw new Error("nothing in the making");
        try {
          return { ...target, translation: await translateFor(text, target.side) };
        } catch (e) {
          if (find(target.id)?.original.trim() === text) patch(target.id, { status: "failed" });
          throw e;
        }
      },
      (text, result) => {
        lastLive.current = { id: result.id, text, translation: result.translation };
        const turn = find(result.id);
        if (!turn || turn.status === "done" || turn.status === "failed") return;
        const complete = turn.original.trim() === text;
        if (complete) patch(result.id, { translation: result.translation, status: turn.status === "transcribing" ? "transcribing" : "done" });
        else if (turn.original.startsWith(text)) patch(result.id, { translation: result.translation });
      },
      1500,
    );
    return () => live.current?.cancel();
  }, [patch, translateFor]);

  const scheduleLive = useCallback((id: string, side: Side, text: string) => {
    liveFor.current = { id, side };
    live.current?.schedule(text.trim());
  }, []);

  /** A sentence that loses the floor gets its complete translation, if it has none yet. */
  const settle = useCallback((id: string) => {
    const turn = find(id);
    if (!turn || (turn.status !== "translating" && turn.status !== "pending")) return;
    const text = turn.original.trim();
    if (!text) return;
    const last = lastLive.current;
    if (last && last.id === id && last.text === text) patch(id, { translation: last.translation, status: "done" });
    else void translate(id, text, turn.side);
  }, [patch, translate]);

  // --- listening ----------------------------------------------------------------------------

  const finishListening = useCallback(() => {
    const side = recordingRef.current;
    if (!side) return;
    recordingRef.current = null;
    setRecording(null);
    setQuiet(false);
    setEndingSoon(false);
    // The microphone finishes on its own, the sentence waits for the complete transcript.
    recorder.stop();
  }, [recorder]);

  /** The final transcript arrived, the sentence takes its place. */
  const finalize = useCallback((id: string, side: Side, text: string) => {
    const turn = find(id);
    if (!turn || turn.status !== "transcribing") return;
    const clean = text.trim() || turn.original.trim();
    if (!clean) {
      patch(id, { original: "", translation: "", status: "done" });
      setNotice({ side, kind: "empty" });
      return;
    }
    const last = lastLive.current;
    if (last && last.id === id && last.text === clean) {
      patch(id, { original: clean, translation: last.translation, status: "done" });
      return;
    }
    patch(id, { original: clean });
    void translate(id, clean, side);
  }, [patch, translate]);

  const startListening = useCallback((side: Side) => {
    if (endedRef.current) return;
    if (recordingRef.current) finishListening();
    const current = floorRef.current;
    if (current?.id) settle(current.id);
    setNotice(null);
    setEndingSoon(false);
    const { sttProviderId, langOf } = optionsRef.current;
    const id = newId();
    addTurn({ id, side, source: "spoken", original: "", translation: "", status: "transcribing", at: Date.now(), edited: false });
    setFloor({ side, id });
    recordingRef.current = side;
    setRecording(side);
    void recorder.start({
      providerId: sttProviderId,
      language: localeOf(langOf(side)),
      onPartial: (text) => {
        if (!text.trim() || find(id)?.status !== "transcribing") return;
        patch(id, { original: text });
        // A late window still improves the sentence, but only the open one keeps translating.
        if (recordingRef.current === side && floorRef.current?.id === id) scheduleLive(id, side, text);
      },
      onFinal: (text) => finalize(id, side, text),
      onQuiet: (isQuiet) => {
        if (recordingRef.current === side) setQuiet(isQuiet);
      },
      onEndingSoon: () => {
        if (recordingRef.current === side) setEndingSoon(true);
      },
      onAutoStop: () => {
        if (recordingRef.current !== side) return;
        recordingRef.current = null;
        setRecording(null);
        setQuiet(false);
        setEndingSoon(false);
      },
      onError: (kind) => {
        setNotice({ side, kind });
        if (kind === "mic" && recordingRef.current === side) {
          recordingRef.current = null;
          setRecording(null);
          setQuiet(false);
          setEndingSoon(false);
          patch(id, { status: "done" });
        }
      },
    });
  }, [addTurn, finalize, finishListening, patch, recorder, scheduleLive, setFloor, settle]);

  const toggleMic = useCallback((side: Side) => {
    if (recordingRef.current === side) finishListening();
    else startListening(side);
  }, [finishListening, startListening]);

  // --- typing -------------------------------------------------------------------------------

  /** This side takes the floor without a word yet, its field is empty and ready. */
  const begin = useCallback((side: Side) => {
    if (endedRef.current) return;
    if (recordingRef.current && recordingRef.current !== side) finishListening();
    const current = floorRef.current;
    if (current?.side === side) return;
    if (current?.id) settle(current.id);
    setFloor({ side, id: null });
  }, [finishListening, setFloor, settle]);

  /** What the field of this side says now, a new sentence or a correction of the one it holds. Typed text waits for Enter. */
  const type = useCallback((side: Side, text: string) => {
    if (endedRef.current || recordingRef.current === side) return;
    if (recordingRef.current) finishListening();
    let current = floorRef.current;
    if (!current || current.side !== side) {
      if (current?.id) settle(current.id);
      const last = turnsRef.current[turnsRef.current.length - 1];
      current = !current && last && last.side === side ? { side, id: last.id } : { side, id: null };
      setFloor(current);
    }
    const clean = text.trim();
    if (current.id) {
      const turn = find(current.id);
      if (!turn) return;
      if (!clean) {
        live.current?.cancel();
        patch(current.id, { original: text, translation: "", status: "done" });
        return;
      }
      if (clean === turn.original.trim()) {
        patch(current.id, { original: text });
        return;
      }
      patch(current.id, { original: text, status: "pending", edited: turn.edited || turn.source === "spoken" });
      return;
    }
    if (!clean) return;
    const id = newId();
    addTurn({ id, side, source: "typed", original: text, translation: "", status: "pending", at: Date.now(), edited: false });
    setFloor({ side, id });
  }, [addTurn, finishListening, patch, setFloor, settle]);

  /** Enter, the button or leaving the field: the typed sentence goes to the translation as a whole. */
  const translateTyped = useCallback((side: Side) => {
    const current = floorRef.current;
    if (!current?.id || current.side !== side) return;
    const turn = find(current.id);
    if (!turn || turn.status !== "pending") return;
    const text = turn.original.trim();
    if (text) void translate(turn.id, text, side);
  }, [translate]);

  // --- whole conversation -------------------------------------------------------------------

  const stopEverything = useCallback(() => {
    live.current?.cancel();
    recorder.cancel();
    recordingRef.current = null;
    setRecording(null);
    setQuiet(false);
    setEndingSoon(false);
  }, [recorder]);

  /** Ends the conversation, everything stays readable, nobody speaks any more. */
  const end = useCallback(async () => {
    stopEverything();
    setEnded(true);
    const current = floorRef.current;
    const turn = current?.id ? find(current.id) : undefined;
    if (!turn || turn.status === "done" || turn.status === "failed") return;
    const text = turn.original.trim();
    if (!text) {
      patch(turn.id, { status: "done" });
      return;
    }
    // A sentence cut off by the end still gets its complete translation.
    await translate(turn.id, text, turn.side);
  }, [patch, setEnded, stopEverything, translate]);

  // How full the conversation is, the translation does not count against anyone.
  const chars = countChars(turns);
  const fill = charState(chars);

  // A full conversation ends by itself, everything stays readable and a new one is one click away.
  useEffect(() => {
    if (fill === "full" && !endedRef.current) void end();
  }, [fill, end]);

  const reset = useCallback(() => {
    stopEverything();
    commit([]);
    sent.current.clear();
    setFloor(null);
    setEnded(false);
    setNotice(null);
  }, [commit, setEnded, setFloor, stopEverything]);

  /** A conversation from the server, to read or to continue. */
  const load = useCallback((saved: Turn[], isEnded: boolean) => {
    stopEverything();
    // A sentence saved in the middle of its translation waits for Enter again.
    const settled = saved.map((turn) => (turn.status === "done" || turn.status === "failed" ? turn : { ...turn, status: "pending" as const }));
    commit(settled.sort(byTime));
    sent.current = new Set(saved.map((turn) => turn.id));
    setFloor(null);
    setEnded(isEnded);
    setNotice(null);
  }, [commit, setEnded, setFloor, stopEverything]);

  /** The two people change seats, their sentences move with them. */
  const flipSides = useCallback(() => {
    stopEverything();
    setFloor(null);
    commit(turnsRef.current.map((turn) => ({ ...turn, side: otherSide(turn.side) })));
  }, [commit, setFloor, stopEverything]);

  /** One person switches language, every column keeps showing its own language. */
  const flipTexts = useCallback(() => {
    stopEverything();
    setFloor(null);
    commit(turnsRef.current.map((turn) => ({ ...turn, original: turn.translation, translation: turn.original })));
  }, [commit, setFloor, stopEverything]);

  return { turns, recording, quiet, endingSoon, fill, floor, ended, notice, begin, type, translateTyped, toggleMic, finish: finishListening, end, reset, load, flipSides, flipTexts };
}

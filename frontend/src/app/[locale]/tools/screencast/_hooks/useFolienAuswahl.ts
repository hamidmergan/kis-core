"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { SlideData } from "@/types";
import { geaenderteFolien, type VertonterStand } from "../_utils";
import { ohneTonAberMitSkript, startAuswahl, type GespeicherteAuswahl } from "./_auswahl";

interface Optionen {
  slides: SlideData[];
  stand: VertonterStand | null;
  hatTon: boolean[];
  gespeichert: GespeicherteAuswahl | null;
  bereit: boolean;
}

/** Die beiden Mengen aus Schritt 6, samt Vorbelegung und Sperren. */
export function useFolienAuswahl({ slides, stand, hatTon, gespeichert, bereit }: Optionen) {
  const [imScreencast, setImScreencast] = useState<number[]>([]);
  const [neuVertonen, setNeuVertonen] = useState<number[]>([]);
  const vorbelegt = useRef(false);

  const scripts = useMemo(() => slides.map((s) => s.script ?? ""), [slides]);
  const geaendert = useMemo(() => geaenderteFolien(stand, slides), [stand, slides]);
  const gesperrtNeu = useMemo(
    () => new Set(ohneTonAberMitSkript(scripts, hatTon)),
    [scripts, hatTon],
  );

  useEffect(() => {
    if (!bereit || vorbelegt.current || !slides.length) return;
    const start = startAuswahl(slides.length, gespeichert, geaendert, hatTon, scripts);
    setImScreencast(start.imScreencast);
    setNeuVertonen(start.neuVertonen);
    vorbelegt.current = true;
  }, [bereit, slides.length, gespeichert, geaendert, hatTon, scripts]);

  const umschaltenScreencast = useCallback((i: number) => {
    setImScreencast((alt) => (alt.includes(i) ? alt.filter((x) => x !== i) : [...alt, i].sort((a, b) => a - b)));
    // Eine Folie ausserhalb des Screencasts wird nicht vertont.
    setNeuVertonen((alt) => alt.filter((x) => x !== i));
  }, []);

  const umschaltenNeu = useCallback((i: number) => {
    if (gesperrtNeu.has(i)) return;
    setNeuVertonen((alt) => (alt.includes(i) ? alt.filter((x) => x !== i) : [...alt, i].sort((a, b) => a - b)));
  }, [gesperrtNeu]);

  const alleNummern = useMemo(() => slides.map((_, i) => i), [slides]);

  const setzeAlle = useCallback((zeigtNeu: boolean) => {
    if (zeigtNeu) setNeuVertonen(alleNummern.filter((i) => imScreencast.includes(i) && scripts[i]?.trim()));
    else setImScreencast(alleNummern);
  }, [alleNummern, imScreencast, scripts]);

  const setzeKeine = useCallback((zeigtNeu: boolean) => {
    if (zeigtNeu) setNeuVertonen([...gesperrtNeu].filter((i) => imScreencast.includes(i)).sort((a, b) => a - b));
    else setImScreencast([]);
  }, [gesperrtNeu, imScreencast]);

  const setzeGeaenderte = useCallback(() => {
    const menge = new Set([...geaendert, ...gesperrtNeu]);
    setNeuVertonen([...menge].filter((i) => imScreencast.includes(i)).sort((a, b) => a - b));
  }, [geaendert, gesperrtNeu, imScreencast]);

  return {
    imScreencast, neuVertonen, geaendert, gesperrtNeu,
    umschaltenScreencast, umschaltenNeu, setzeAlle, setzeKeine, setzeGeaenderte,
  };
}

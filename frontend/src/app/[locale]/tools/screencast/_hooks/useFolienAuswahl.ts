"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { SlideData } from "@/types";
import { geaenderteFolien, type VertonterStand } from "../_utils";
import { angleichen, ohneTonAberMitSkript, startAuswahl, type GespeicherteAuswahl } from "./_auswahl";

interface Optionen {
  slides: SlideData[];
  stand: VertonterStand | null;
  hatTon: boolean[];
  gespeichert: GespeicherteAuswahl | null;
  bereit: boolean;
}

/** The two sets from step 6, with their preselection. */
export function useFolienAuswahl({ slides, stand, hatTon, gespeichert, bereit }: Optionen) {
  const [imScreencast, setImScreencast] = useState<number[]>([]);
  const [neuVertonen, setNeuVertonen] = useState<number[]>([]);
  const vorbelegtFuer = useRef<boolean[] | null>(null);

  const scripts = useMemo(() => slides.map((s) => s.script ?? ""), [slides]);
  const geaendert = useMemo(() => geaenderteFolien(stand, slides), [stand, slides]);
  const ohneTon = useMemo(
    () => new Set(ohneTonAberMitSkript(scripts, hatTon)),
    [scripts, hatTon],
  );

  useEffect(() => {
    // A newly fetched state may trigger the preselection again.
    if (!bereit || !slides.length || vorbelegtFuer.current === hatTon) return;
    const start = startAuswahl(slides.length, gespeichert);
    setImScreencast(start.imScreencast);
    setNeuVertonen(start.neuVertonen);
    vorbelegtFuer.current = hatTon;
  }, [bereit, slides.length, gespeichert, hatTon]);

  const setzeScreencast = useCallback((naechste: number[]) => {
    setImScreencast(naechste);
    setNeuVertonen((alt) => angleichen(naechste, alt));
  }, []);

  const umschaltenScreencast = useCallback((i: number) => {
    setzeScreencast(
      imScreencast.includes(i)
        ? imScreencast.filter((x) => x !== i)
        : [...imScreencast, i].sort((a, b) => a - b),
    );
  }, [imScreencast, setzeScreencast]);

  const umschaltenNeu = useCallback((i: number) => {
    setNeuVertonen((alt) => (alt.includes(i) ? alt.filter((x) => x !== i) : [...alt, i].sort((a, b) => a - b)));
  }, []);

  const alleNummern = useMemo(() => slides.map((_, i) => i), [slides]);

  const setzeAlle = useCallback((zeigtNeu: boolean) => {
    if (zeigtNeu) setNeuVertonen(alleNummern.filter((i) => imScreencast.includes(i) && scripts[i]?.trim()));
    else setzeScreencast(alleNummern);
  }, [alleNummern, imScreencast, scripts, setzeScreencast]);

  const setzeKeine = useCallback((zeigtNeu: boolean) => {
    if (zeigtNeu) setNeuVertonen([]);
    else setzeScreencast([]);
  }, [setzeScreencast]);

  const setzeGeaenderte = useCallback(() => {
    setNeuVertonen(geaendert.filter((i) => imScreencast.includes(i)).sort((a, b) => a - b));
  }, [geaendert, imScreencast]);

  return {
    imScreencast, neuVertonen, geaendert, ohneTon,
    umschaltenScreencast, umschaltenNeu, setzeAlle, setzeKeine, setzeGeaenderte,
  };
}

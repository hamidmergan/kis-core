import { useCallback, useEffect, useRef, useState } from "react";

/** A horizontal strip of tiles: knows whether it can scroll either way and keeps the active tile in view. */
export function useTileStrip(tileCount: number, activeKey: unknown) {
  const streifenRef = useRef<HTMLDivElement>(null);
  const [kannLinks, setKannLinks] = useState(false);
  const [kannRechts, setKannRechts] = useState(false);

  const messen = useCallback(() => {
    const el = streifenRef.current;
    if (!el) return;
    setKannLinks(el.scrollLeft > 1);
    setKannRechts(el.scrollLeft + el.clientWidth < el.scrollWidth - 1);
  }, []);

  useEffect(() => {
    const el = streifenRef.current;
    if (!el) return;
    messen();
    el.addEventListener("scroll", messen, { passive: true });
    window.addEventListener("resize", messen);
    return () => {
      el.removeEventListener("scroll", messen);
      window.removeEventListener("resize", messen);
    };
  }, [messen, tileCount]);

  // The shown tile has to stay visible even when the stage moves on by itself.
  useEffect(() => {
    const el = streifenRef.current;
    if (!el) return;
    const kachel = el.querySelector<HTMLElement>('[data-aktiv="true"]');
    if (!kachel) return;
    const aussen = el.getBoundingClientRect();
    const innen = kachel.getBoundingClientRect();
    el.scrollBy({ left: innen.left - aussen.left - aussen.width / 2 + innen.width / 2, behavior: "smooth" });
  }, [activeKey]);

  /** A click moves by one tile width, measured on the first tile. */
  const schieben = useCallback((richtung: -1 | 1) => {
    const el = streifenRef.current;
    if (!el) return;
    const breite = el.querySelector("button")?.getBoundingClientRect().width ?? 74;
    el.scrollBy({ left: richtung * (breite + 8), behavior: "smooth" });
  }, []);

  return { streifenRef, kannLinks, kannRechts, schieben };
}

"use client";

import { useLayoutEffect, type RefObject } from "react";

const STEP = 0.05;

/** Lowers the page zoom from its media query value until the hero fits on one screen, it never raises it. */
export function useFitZoom(ref: RefObject<HTMLElement | null>, heroTestId: string) {
  useLayoutEffect(() => {
    const main = ref.current;
    if (!main) return;
    const heroFits = () => {
      const hero = document.querySelector(`[data-testid="${heroTestId}"]`);
      // Document position, so the check does not depend on how far the page is scrolled.
      return !hero || hero.getBoundingClientRect().bottom + window.scrollY <= window.innerHeight + 1;
    };
    const fit = () => {
      // Back to the value the media queries give, then step down.
      main.style.removeProperty("--zoom");
      const start = parseFloat(getComputedStyle(main).getPropertyValue("--zoom")) || 1;
      if (heroFits()) return;
      for (let zoom = start - STEP; zoom >= 1 - 1e-6; zoom -= STEP) {
        main.style.setProperty("--zoom", zoom.toFixed(2));
        if (heroFits()) return;
      }
    };
    fit();
    let timer = 0;
    const onResize = () => {
      window.clearTimeout(timer);
      timer = window.setTimeout(fit, 100);
    };
    window.addEventListener("resize", onResize);
    window.addEventListener("bandtop", onResize);
    // Web fonts change the line breaks once they are loaded.
    void document.fonts?.ready.then(fit);
    return () => {
      window.clearTimeout(timer);
      window.removeEventListener("resize", onResize);
      window.removeEventListener("bandtop", onResize);
      main.style.removeProperty("--zoom");
    };
  }, [ref, heroTestId]);
}

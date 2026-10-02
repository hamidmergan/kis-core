"use client";

import { useLayoutEffect } from "react";

/** Writes the distance from the page top to the element with this test id into --band-top. */
export function useBandTop(testId: string) {
  useLayoutEffect(() => {
    const root = document.documentElement;
    const measure = () => {
      const el = document.querySelector(`[data-testid="${testId}"]`);
      if (el) root.style.setProperty("--band-top", `${el.getBoundingClientRect().top + window.scrollY}px`);
    };
    measure();
    window.addEventListener("resize", measure);
    return () => {
      window.removeEventListener("resize", measure);
      root.style.removeProperty("--band-top");
    };
  }, [testId]);
}

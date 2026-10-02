"use client";

import { useLayoutEffect } from "react";

/** Writes the distance from the page top to the element with this test id into --band-top, and keeps it current. */
export function useBandTop(testId: string) {
  useLayoutEffect(() => {
    const root = document.documentElement;
    const el = document.querySelector(`[data-testid="${testId}"]`);
    if (!el) return;
    const measure = () => {
      const top = `${Math.round(el.getBoundingClientRect().top + window.scrollY)}px`;
      if (root.style.getPropertyValue("--band-top") === top) return;
      root.style.setProperty("--band-top", top);
      window.dispatchEvent(new Event("bandtop"));
    };
    measure();
    window.addEventListener("resize", measure);
    // Whatever sits above the band shifts it when it changes height, for example the header after hydration.
    const observer = new ResizeObserver(measure);
    for (let node: Element | null = el; node && node !== document.body; node = node.parentElement) {
      for (let sibling = node.previousElementSibling; sibling; sibling = sibling.previousElementSibling) observer.observe(sibling);
    }
    return () => {
      window.removeEventListener("resize", measure);
      observer.disconnect();
      root.style.removeProperty("--band-top");
    };
  }, [testId]);
}

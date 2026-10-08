"use client";

import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { useTranslations } from "next-intl";
import { ArrowUp } from "@phosphor-icons/react";

/** Appears after a long scroll and brings the visitor back to the top of the page. */
export default function ScrollTopButton() {
  const t = useTranslations("eventInfo");
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const update = () => setVisible(window.scrollY > window.innerHeight);
    update();
    window.addEventListener("scroll", update, { passive: true });
    return () => window.removeEventListener("scroll", update);
  }, []);

  if (!visible) return null;
  const toTop = () => {
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    window.scrollTo({ top: 0, behavior: reduce ? "auto" : "smooth" });
  };
  // The page is zoomed on wide screens, a fixed button inside it would be scaled and shifted, so it goes to the body.
  return createPortal(
    <button
      type="button"
      onClick={toTop}
      aria-label={t("toTop")}
      className="fixed bottom-6 right-6 z-40 flex items-center justify-center w-10 h-10 rounded-full btn-icon border border-border bg-background shadow-sm transition-colors print:hidden"
      data-testid="scroll-top"
    >
      <ArrowUp size={18} weight="bold" aria-hidden="true" />
    </button>,
    document.body,
  );
}

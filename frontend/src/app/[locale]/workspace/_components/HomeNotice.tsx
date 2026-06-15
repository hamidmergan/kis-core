"use client";

import { useEffect, useRef, useState } from "react";
import { CaretDown } from "@phosphor-icons/react";
import { api } from "@/lib/api";

interface Notice {
  enabled: boolean;
  text: string;
}

// Collapsed window ~3 lines (text-sm line-height 1.25rem * 3).
const COLLAPSED_MAX_HEIGHT = "3.75rem";
// Fade the last line into nothing so it reads as "there's more below".
const FADE_MASK = "linear-gradient(to bottom, black 45%, transparent 100%)";

/**
 * Admin-configurable notice banner for the start page. Shown to all users
 * (any role) above "Nächste Termine". Reads the public /health/labels probe
 * so it renders without auth/admin rights. Renders nothing unless the admin
 * enabled it AND left a non-empty text.
 *
 * Long texts are collapsed to ~3 lines by default with a soft fade at the
 * bottom; a subtle caret toggles the full text. Short texts show in full
 * without a toggle.
 */
export default function HomeNotice() {
  const [notice, setNotice] = useState<Notice | null>(null);
  const [expanded, setExpanded] = useState(false);
  const [showToggle, setShowToggle] = useState(false);
  const [fullHeight, setFullHeight] = useState(0);
  const textRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .fetch("/api/health/labels", { cache: "no-store" })
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (cancelled || !data) return;
        setNotice({
          enabled: data.home_notice_enabled === true,
          text: typeof data.home_notice_text === "string" ? data.home_notice_text : "",
        });
      })
      .catch(() => {
        /* ignore - banner is non-critical */
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // Once the text is in the DOM (still collapsed), check whether it is taller
  // than the 3-line window. Only then do we show the fade + toggle.
  useEffect(() => {
    const el = textRef.current;
    if (!el) return;
    setFullHeight(el.scrollHeight);
    setShowToggle(el.scrollHeight > el.clientHeight + 4);
  }, [notice]);

  if (!notice || !notice.enabled || !notice.text.trim()) return null;

  const collapsed = !expanded && showToggle;

  return (
    <div className="mb-10 flex justify-center">
      <div
        className="max-w-2xl w-full rounded-xl border border-warn-border bg-warn-bg px-5 py-4 text-sm text-warn-strong"
        role="status"
      >
        <div
          ref={textRef}
          className="text-center whitespace-pre-line overflow-hidden transition-[max-height] duration-300 ease-in-out"
          style={{
            maxHeight: expanded ? `${fullHeight}px` : COLLAPSED_MAX_HEIGHT,
            maskImage: collapsed ? FADE_MASK : undefined,
            WebkitMaskImage: collapsed ? FADE_MASK : undefined,
          }}
        >
          {notice.text}
        </div>
        {showToggle && (
          <button
            type="button"
            onClick={() => setExpanded((v) => !v)}
            aria-expanded={expanded}
            aria-label={expanded ? "Hinweis einklappen" : "Hinweis ausklappen"}
            className="mx-auto mt-1.5 flex items-center justify-center opacity-50 hover:opacity-90 transition-opacity"
          >
            <CaretDown
              size={16}
              weight="bold"
              className={`transition-transform duration-300 ${expanded ? "rotate-180" : ""}`}
            />
          </button>
        )}
      </div>
    </div>
  );
}

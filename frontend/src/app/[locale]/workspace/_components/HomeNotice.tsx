"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";
import { CaretDown, X } from "@phosphor-icons/react";
import { api } from "@/lib/api";
import { HOME_NOTICE_DISMISS_KEY, HOME_NOTICE_SHOW_EVENT } from "@/lib/constants";
import IconButton from "@/components/ui/IconButton";

interface Notice {
  enabled: boolean;
  text: string;
}

// Collapsed window ~3 lines (text-sm line-height 1.25rem * 3).
const COLLAPSED_MAX_HEIGHT = "3.75rem";
// Fade the last line into nothing so it reads as "there's more below".
const FADE_MASK = "linear-gradient(to bottom, black 45%, transparent 100%)";

// Inline [label](url) links, written straight into the admin's free text.
const LINK_PATTERN = /\[([^\]]+)\]\((\S+?)\)/g;

function renderNoticeText(text: string): ReactNode[] {
  const parts: ReactNode[] = [];
  let lastIndex = 0;
  let match: RegExpExecArray | null;
  LINK_PATTERN.lastIndex = 0;
  while ((match = LINK_PATTERN.exec(text))) {
    if (match.index > lastIndex) parts.push(text.slice(lastIndex, match.index));
    parts.push(
      <a
        key={match.index}
        href={match[2]}
        className="underline font-medium hover:opacity-80 transition-opacity"
      >
        {match[1]}
      </a>
    );
    lastIndex = match.index + match[0].length;
  }
  if (lastIndex < text.length) parts.push(text.slice(lastIndex));
  return parts;
}

/** Notice banner of the start page, reads the public probe and stays empty without text. */
export default function HomeNotice() {
  const [notice, setNotice] = useState<Notice | null>(null);
  const [dismissed, setDismissed] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const [showToggle, setShowToggle] = useState(false);
  const [fullHeight, setFullHeight] = useState(0);
  const wrapRef = useRef<HTMLDivElement>(null);
  const textRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .fetch("/api/health/labels", { cache: "no-store" })
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (cancelled || !data) return;
        const text = typeof data.home_notice_text === "string" ? data.home_notice_text : "";
        let dismissedText: string | null = null;
        try {
          dismissedText = localStorage.getItem(HOME_NOTICE_DISMISS_KEY);
        } catch {
          /* ignore - private browsing etc. */
        }
        setNotice({
          enabled: data.home_notice_enabled === true,
          text,
        });
        setDismissed(dismissedText !== null && dismissedText === text);
      })
      .catch(() => {
        /* ignore - banner is non-critical */
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // Only in the DOM does it show whether the text is taller than three lines.
  // Re-measures when a dismissed notice comes back (its DOM only exists once dismissed is false).
  useEffect(() => {
    const el = textRef.current;
    if (!el) return;
    setFullHeight(el.scrollHeight);
    setShowToggle(el.scrollHeight > el.clientHeight + 4);
  }, [notice, dismissed]);

  // Lets the header settings menu bring a dismissed (or already visible) notice back into view.
  useEffect(() => {
    const handleShow = () => {
      try {
        localStorage.removeItem(HOME_NOTICE_DISMISS_KEY);
      } catch {
        /* ignore */
      }
      setDismissed(false);
      setExpanded(true);
      wrapRef.current?.scrollIntoView({ behavior: "smooth", block: "center" });
    };
    window.addEventListener(HOME_NOTICE_SHOW_EVENT, handleShow);
    return () => window.removeEventListener(HOME_NOTICE_SHOW_EVENT, handleShow);
  }, []);

  if (!notice || !notice.enabled || !notice.text.trim() || dismissed) return null;

  const collapsed = !expanded && showToggle;

  const handleClose = () => {
    try {
      localStorage.setItem(HOME_NOTICE_DISMISS_KEY, notice.text);
    } catch {
      /* ignore */
    }
    setDismissed(true);
  };

  return (
    <div className="mb-10 flex justify-center" ref={wrapRef}>
      <div
        className="max-w-2xl w-full rounded-xl bg-info-bg px-5 py-4 text-sm text-kb-dark flex items-start gap-2"
        role="status"
      >
        <span className="w-7 h-7 shrink-0" aria-hidden="true" />
        <div className="flex-1 min-w-0">
          <div
            ref={textRef}
            className="text-center whitespace-pre-line break-words overflow-hidden transition-[max-height] duration-300 ease-in-out"
            style={{
              maxHeight: expanded ? `${fullHeight}px` : COLLAPSED_MAX_HEIGHT,
              maskImage: collapsed ? FADE_MASK : undefined,
              WebkitMaskImage: collapsed ? FADE_MASK : undefined,
            }}
          >
            {renderNoticeText(notice.text)}
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
        <IconButton onClick={handleClose} aria-label="Hinweis schließen" className="shrink-0">
          <X size={13} weight="bold" />
        </IconButton>
      </div>
    </div>
  );
}

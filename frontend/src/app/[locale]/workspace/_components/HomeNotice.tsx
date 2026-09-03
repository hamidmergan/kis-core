"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";
import { useTranslations } from "next-intl";
import { CaretDown, X } from "@phosphor-icons/react";
import { api } from "@/lib/api";
import { HOME_NOTICE_DISMISS_KEY, HOME_NOTICE_SHOW_EVENT } from "@/lib/constants";
import IconButton from "@/components/ui/IconButton";

interface Notice {
  enabled: boolean;
  text: string;
}

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

/** Full-width notice bar above the header on the start page, collapsed to a single word until it is opened. */
export default function HomeNotice() {
  const t = useTranslations("homeNotice");
  const [notice, setNotice] = useState<Notice | null>(null);
  const [dismissed, setDismissed] = useState(false);
  const [expanded, setExpanded] = useState(false);
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

  // The open height is only measurable in the DOM, and the text only exists there once it is neither empty nor dismissed.
  useEffect(() => {
    const el = textRef.current;
    if (!el) return;
    setFullHeight(el.scrollHeight);
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

  const handleClose = () => {
    try {
      localStorage.setItem(HOME_NOTICE_DISMISS_KEY, notice.text);
    } catch {
      /* ignore */
    }
    setDismissed(true);
  };

  return (
    <div
      className="w-full bg-info-bg text-kb-dark px-4 sm:px-6 py-2"
      role="status"
      ref={wrapRef}
    >
      <div className="text-sm flex items-start gap-2">
        <span className="w-7 h-7 shrink-0" aria-hidden="true" />
        <div className="flex-1 min-w-0">
          <div
            ref={textRef}
            inert={!expanded}
            className="max-w-3xl mx-auto text-center whitespace-pre-line break-words overflow-hidden transition-[max-height] duration-300 ease-in-out"
            style={{ maxHeight: expanded ? `${fullHeight}px` : 0 }}
          >
            {renderNoticeText(notice.text)}
          </div>
          <button
            type="button"
            onClick={() => setExpanded((v) => !v)}
            aria-expanded={expanded}
            aria-label={expanded ? t("collapse") : t("expand")}
            className={`mx-auto flex items-center justify-center gap-1 opacity-70 hover:opacity-100 transition-opacity${expanded ? " mt-1.5" : ""}`}
          >
            {!expanded && <span className="font-medium">{t("label")}</span>}
            <CaretDown
              size={16}
              weight="bold"
              className={`transition-transform duration-300 ${expanded ? "rotate-180" : ""}`}
            />
          </button>
        </div>
        <IconButton onClick={handleClose} aria-label={t("close")} className="shrink-0">
          <X size={13} weight="bold" />
        </IconButton>
      </div>
    </div>
  );
}

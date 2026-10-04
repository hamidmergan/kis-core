"use client";

import { useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { ArrowSquareOut, FileText, Globe, MapPin } from "@phosphor-icons/react";
import Modal from "@/components/ui/Modal";
import type { CampusQuelle } from "../_types";

/** The link with a text fragment, so supporting browsers jump to the passage. */
export function quellenLink(q: CampusQuelle): string | null {
  if (!q.url) return null;
  if (!q.fragment) return q.url;
  return `${q.url}#:~:text=${encodeURIComponent(q.fragment)}`;
}

function domain(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
}

function standText(date: string | null, locale: string): string | null {
  if (!date) return null;
  const d = new Date(`${date}T00:00:00`);
  if (Number.isNaN(d.getTime())) return date;
  return d.toLocaleDateString(locale === "en" ? "en-GB" : "de-DE", { day: "2-digit", month: "2-digit", year: "numeric" });
}

/** Quiet one-line chip, shared by the source and place chips. */
export const CHIP_KLASSE = "inline-flex items-center gap-1.5 px-3 py-1 rounded-full border-2 border-transparent bg-background text-xs min-w-0 max-w-full no-underline";
export const CHIP_HOVER = "hover:border-kb focus:border-kb transition-colors";

/** Domain or file name with the date, shown under each source in the dialog. */
function quellenInfo(q: CampusQuelle, locale: string, t: ReturnType<typeof useTranslations>) {
  const stand = standText(q.fetched_at, locale);
  const sub = q.kind === "document" ? q.filename ?? t("document") : q.url ? domain(q.url) : "";
  const detail = sub && `${sub}${stand ? `, ${t("stand", { date: stand })}` : ""}`;
  return { detail };
}

export default function QuellenKarten({ quellen }: { quellen: CampusQuelle[] }) {
  const t = useTranslations("tools.campus");
  const locale = useLocale();
  const [offen, setOffen] = useState(false);
  if (quellen.length === 0) return null;
  return (
    <>
      <button type="button" onClick={() => setOffen(true)} data-testid="campus-sources" className={`${CHIP_KLASSE} ${CHIP_HOVER}`} style={{ color: "var(--muted)" }}>
        <FileText size={14} weight="fill" style={{ color: "var(--muted)", flexShrink: 0 }} />
        <span>{t("sourcesTitle")} ({quellen.length})</span>
      </button>
      <Modal open={offen} onClose={() => setOffen(false)} title={t("sourcesTitle")} size="md">
        <ul className="flex flex-col gap-2" data-testid="campus-sources-list">
          {quellen.map((q) => {
            const href = quellenLink(q);
            const info = quellenInfo(q, locale, t);
            const Icon = q.kind === "document" ? FileText : q.kind === "place" ? MapPin : Globe;
            const inner = (
              <>
                <Icon size={18} weight="bold" style={{ color: "var(--kb)", flexShrink: 0 }} />
                <span className="min-w-0 flex-1">
                  <span className="block text-sm font-medium break-words" style={{ color: "var(--foreground)" }}>{q.title}</span>
                  {info.detail && <span className="block text-xs mt-0.5" style={{ color: "var(--muted)" }}>{info.detail}</span>}
                </span>
                {href && <ArrowSquareOut size={14} weight="bold" style={{ color: "var(--muted)", flexShrink: 0 }} />}
              </>
            );
            const klasse = "flex items-center gap-3 px-3 py-2 rounded-xl border-2 border-border min-w-0 no-underline";
            return (
              <li key={q.page_id} className="min-w-0">
                {href ? (
                  <a href={href} target="_blank" rel="noopener noreferrer" className={`${klasse} hover:border-kb focus:border-kb transition-colors`}>{inner}</a>
                ) : (
                  <div className={klasse}>{inner}</div>
                )}
              </li>
            );
          })}
        </ul>
      </Modal>
    </>
  );
}

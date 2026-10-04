"use client";

import { useLocale, useTranslations } from "next-intl";
import { ArrowSquareOut, FileText, Globe, MapPin } from "@phosphor-icons/react";
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

export default function QuellenKarten({ quellen }: { quellen: CampusQuelle[] }) {
  const t = useTranslations("tools.campus");
  const locale = useLocale();
  if (quellen.length === 0) return null;
  return (
    <div className="mt-2" data-testid="campus-sources">
      <p className="text-2xs font-semibold uppercase tracking-wide mb-1" style={{ color: "var(--muted)" }}>{t("sourcesTitle")}</p>
      <div className="flex flex-wrap gap-2">
        {quellen.map((q) => {
          const href = quellenLink(q);
          const Icon = q.kind === "document" ? FileText : q.kind === "place" ? MapPin : Globe;
          const stand = standText(q.fetched_at, locale);
          const sub = q.kind === "document" ? q.filename ?? t("document") : q.url ? domain(q.url) : "";
          const inner = (
            <>
              <Icon size={16} weight="bold" style={{ color: "var(--kb)", flexShrink: 0 }} />
              <span className="min-w-0">
                <span className="block text-sm font-medium truncate" style={{ color: "var(--foreground)" }}>{q.title}</span>
                <span className="block text-2xs truncate" style={{ color: "var(--muted)" }}>
                  {sub}
                  {stand && ` · ${t("stand", { date: stand })}`}
                </span>
              </span>
              {href && <ArrowSquareOut size={13} weight="bold" style={{ color: "var(--muted)", flexShrink: 0 }} />}
            </>
          );
          const klasse = "flex items-center gap-2 px-3 py-2 rounded-xl border-2 border-border bg-background max-w-full no-underline";
          return href ? (
            <a key={q.page_id} href={href} target="_blank" rel="noopener noreferrer" className={`${klasse} hover:border-kb focus:border-kb transition-colors`} style={{ maxWidth: 320 }}>
              {inner}
            </a>
          ) : (
            <span key={q.page_id} className={klasse} style={{ maxWidth: 320 }}>
              {inner}
            </span>
          );
        })}
      </div>
    </div>
  );
}

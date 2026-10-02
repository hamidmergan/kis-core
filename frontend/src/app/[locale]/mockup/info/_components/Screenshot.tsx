"use client";

import { useLocale } from "next-intl";

/** Real app screenshot in a light browser frame, one file per language. */
export default function Screenshot({ name, alt, className = "" }: { name: string; alt: string; className?: string }) {
  const locale = useLocale() === "en" ? "en" : "de";
  return (
    <div
      className={`rounded-2xl border border-border bg-background overflow-hidden ${className}`}
      style={{ boxShadow: "var(--shadow)" }}
      data-testid="screenshot"
    >
      <div className="flex items-center gap-1.5 px-4 py-2.5 border-b border-border-soft bg-surface" aria-hidden="true">
        <span className="w-2.5 h-2.5 rounded-full bg-border" />
        <span className="w-2.5 h-2.5 rounded-full bg-border" />
        <span className="w-2.5 h-2.5 rounded-full bg-border" />
      </div>
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={`/mockup/info/${locale}/${name}.webp`} alt={alt} className="block w-full h-auto" loading="lazy" />
    </div>
  );
}

"use client";

import { useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { MapPin } from "@phosphor-icons/react";
import MapModal from "./MapModal";

export interface OrtKarteDaten {
  id: string;
  code: string | null;
  title: { de?: string; en?: string };
  /** What the map's show parameter expects. */
  show: string;
}

/** A card per place an answer mentions, the click opens the campus map at that place. */
export default function OrtKarte({ ort, mapUrl }: { ort: OrtKarteDaten; mapUrl: string }) {
  const t = useTranslations("campusMap");
  const locale = useLocale();
  const [open, setOpen] = useState(false);
  const title = (locale === "en" ? ort.title.en : ort.title.de) || ort.title.de || ort.title.en || ort.id;
  if (!mapUrl) return null;
  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="flex items-center gap-2 px-3 py-2 rounded-xl border-2 border-border hover:border-kb focus:border-kb transition-colors text-left bg-background max-w-full"
        data-testid="campus-place-card"
      >
        <MapPin size={18} weight="fill" style={{ color: "var(--kb)", flexShrink: 0 }} />
        <span className="min-w-0">
          <span className="block text-sm font-medium truncate" style={{ color: "var(--foreground)" }}>{title}</span>
          <span className="block text-2xs" style={{ color: "var(--muted)" }}>{t("showOnMap")}</span>
        </span>
      </button>
      <MapModal open={open} onClose={() => setOpen(false)} mapUrl={mapUrl} show={ort.show} />
    </>
  );
}

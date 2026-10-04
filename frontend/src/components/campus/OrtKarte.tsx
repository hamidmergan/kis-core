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
        className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full border-2 border-transparent hover:border-kb focus:border-kb transition-colors bg-background text-xs max-w-full"
        title={`${title}\n${t("showOnMap")}`}
        data-testid="campus-place-card"
      >
        <MapPin size={14} weight="fill" style={{ color: "var(--muted)", flexShrink: 0 }} />
        <span className="truncate" style={{ color: "var(--muted)", maxWidth: 220 }}>{title}</span>
      </button>
      <MapModal open={open} onClose={() => setOpen(false)} mapUrl={mapUrl} show={ort.show} />
    </>
  );
}

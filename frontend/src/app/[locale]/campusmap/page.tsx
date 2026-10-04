"use client";

import { Suspense, useEffect, useRef, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { useSearchParams } from "next/navigation";

import { campusApi } from "@/lib/campus/api";
import { mapLink } from "@/lib/campus/mapLink";

/** The campus map widget as a page of its own, the target of "open in new tab". */
function CampusMap() {
  const t = useTranslations("campusMap");
  const locale = useLocale();
  const show = useSearchParams().get("show") ?? undefined;
  const [mapUrl, setMapUrl] = useState("");
  const frame = useRef<HTMLIFrameElement>(null);

  useEffect(() => {
    campusApi.map().then((r) => setMapUrl(r.map_url)).catch(() => setMapUrl(""));
  }, []);

  if (!mapUrl) return null;
  return (
    <iframe
      ref={frame}
      onLoad={() => frame.current?.focus()}
      src={mapLink(mapUrl, locale, show, "kis")}
      title={t("title")}
      className="block w-full border-0"
      style={{ height: "100dvh" }}
      allowFullScreen
      allow="clipboard-write"
      referrerPolicy="no-referrer-when-downgrade"
    />
  );
}

export default function CampusMapPage() {
  return (
    <Suspense fallback={null}>
      <CampusMap />
    </Suspense>
  );
}

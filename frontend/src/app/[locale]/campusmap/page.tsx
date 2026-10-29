"use client";

import { Suspense, useEffect, useRef, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { useSearchParams } from "next/navigation";

import { campusApi } from "@/lib/campus/api";
import { getPathname } from "@/i18n/navigation";
import { mapLink } from "@/lib/campus/mapLink";

/** An askFrancis page as a full address, because the map runs in a frame on another origin. */
function absolute(href: string, locale: string): string {
  return window.location.origin + getPathname({ href, locale });
}

/** The campus map widget as a page of its own, the target of "open in new tab". */
function CampusMap() {
  const t = useTranslations("campusMap");
  const locale = useLocale();
  const params = useSearchParams();
  const show = params.get("show") ?? undefined;
  const from = params.get("from") ?? "";
  const [mapUrl, setMapUrl] = useState("");
  const frame = useRef<HTMLIFrameElement>(null);

  useEffect(() => {
    campusApi.map().then((r) => setMapUrl(r.map_url)).catch(() => setMapUrl(""));
  }, []);

  if (!mapUrl) return null;
  const partner = { home: absolute("/workspace", locale), back: absolute(from.startsWith("/") && !from.startsWith("//") ? from : "/services", locale) };
  return (
    <iframe
      ref={frame}
      onLoad={() => frame.current?.focus()}
      src={mapLink(mapUrl, locale, show, partner)}
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

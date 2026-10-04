"use client";

import { useLocale, useTranslations } from "next-intl";
import { ArrowSquareOut } from "@phosphor-icons/react";
import Modal from "@/components/ui/Modal";

/** Builds the map link for one place, with the language of the page. */
export function ortUrl(mapUrl: string, show: string, locale: string): string {
  const base = mapUrl.endsWith("/") ? mapUrl : `${mapUrl}/`;
  const params = new URLSearchParams({ show });
  if (locale !== "de") params.set("lang", locale);
  return `${base}?${params.toString()}`;
}

/** The campus map in a window, so the conversation stays where it is. */
export default function OrtModal({
  open,
  onClose,
  mapUrl,
  show,
  title,
}: {
  open: boolean;
  onClose: () => void;
  mapUrl: string;
  show: string;
  title: string;
}) {
  const t = useTranslations("campusMap");
  const locale = useLocale();
  const url = ortUrl(mapUrl, show, locale);
  return (
    <Modal
      open={open}
      onClose={onClose}
      size="xl"
      title={title}
      footer={
        <>
          <a
            href={url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1.5 px-4 py-2 text-sm rounded-md border-2 border-border text-foreground-soft hover:border-kb transition-colors no-underline"
          >
            <ArrowSquareOut size={15} weight="bold" />
            {t("openInNewTab")}
          </a>
          <button type="button" onClick={onClose} className="px-3 py-2 text-sm btn-primary rounded-md transition-colors">
            {t("close")}
          </button>
        </>
      }
    >
      {open && (
        <iframe
          src={url}
          title={title}
          className="w-full rounded-lg border border-border-soft"
          style={{ height: "70vh", minHeight: 360 }}
          loading="lazy"
          allowFullScreen
        />
      )}
    </Modal>
  );
}

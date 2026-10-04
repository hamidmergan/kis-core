"use client";

import { useLocale, useTranslations } from "next-intl";

import Modal from "@/components/ui/Modal";
import { mapLink } from "@/lib/campus/mapLink";

type Props = { open: boolean; onClose: () => void; mapUrl: string; show?: string };

/** The campus map widget in a dialog, optionally opened on one place. */
export default function MapModal({ open, onClose, mapUrl, show }: Props) {
  const t = useTranslations("campusMap");
  const locale = useLocale();
  const src = mapLink(mapUrl, locale, show);
  return (
    <Modal
      open={open}
      onClose={onClose}
      title={t("title")}
      size="xl"
      footer={
        <a href={src} target="_blank" rel="noopener noreferrer" className="btn-cancel px-4 py-2 text-sm btn-secondary rounded-lg">
          {t("openInNewTab")}
        </a>
      }
    >
      <div className="relative w-full overflow-hidden rounded-lg" style={{ height: "min(70dvh, 560px)" }}>
        <iframe
          src={src}
          title={t("title")}
          className="absolute inset-0 h-full w-full border-0"
          loading="lazy"
          allowFullScreen
          allow="clipboard-write"
          referrerPolicy="no-referrer-when-downgrade"
        />
      </div>
    </Modal>
  );
}

"use client";

import { useRef } from "react";
import { useLocale, useTranslations } from "next-intl";

import Modal from "@/components/ui/Modal";
import { getPathname, usePathname } from "@/i18n/navigation";
import { mapLink } from "@/lib/campus/mapLink";

type Props = { open: boolean; onClose: () => void; mapUrl: string; show?: string };

/** The campus map widget in a dialog, optionally opened on one place. */
export default function MapModal({ open, onClose, mapUrl, show }: Props) {
  const t = useTranslations("campusMap");
  const locale = useLocale();
  const from = usePathname();
  const frame = useRef<HTMLIFrameElement>(null);
  const src = mapLink(mapUrl, locale, show, undefined, true);
  // The new tab stays inside KIS, the page there embeds the same widget and links back to this page.
  const pageHref = getPathname({ href: { pathname: "/campusmap", query: { ...(show ? { show } : {}), from } }, locale });
  return (
    <Modal
      open={open}
      onClose={onClose}
      size="full"
      flush
      title={
        <a href={pageHref} target="_blank" rel="noopener noreferrer" className="btn-cancel px-3 py-1 text-sm btn-secondary rounded-lg">
          {t("openInNewTab")}
        </a>
      }
    >
      <div className="relative w-full overflow-hidden rounded-b-xl" style={{ height: "calc(100dvh - 6rem)" }}>
        <iframe
          ref={frame}
          onLoad={() => frame.current?.focus()}
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

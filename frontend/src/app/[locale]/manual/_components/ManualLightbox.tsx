"use client";

import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useTranslations } from "next-intl";
import { X } from "@phosphor-icons/react";
import { backdropClose, newBackdropPress } from "@/components/ui/backdropClose";

/** Shows one help picture at full size, in the same look as the screencast lightbox. */
export default function ManualLightbox({
  src,
  alt,
  onClose,
}: {
  src: string;
  alt: string;
  onClose: () => void;
}) {
  const t = useTranslations("manual");
  const press = useRef(newBackdropPress());
  const closeRef = useRef<HTMLButtonElement>(null);
  // In the page tree the dialog sits in a foreign stacking context and gets covered.
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    closeRef.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    // The page behind must not scroll away under the picture.
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = previous;
    };
  }, [onClose]);

  if (!mounted) return null;

  return createPortal(
    <div
      className="fixed inset-0 bg-black/80 z-50 flex items-center justify-center p-4 sm:p-8"
      role="dialog"
      aria-modal="true"
      aria-label={alt}
      {...backdropClose(press.current, onClose)}
    >
      <button
        ref={closeRef}
        type="button"
        onClick={onClose}
        aria-label={t("imageClose")}
        className="absolute top-4 right-4 p-2 rounded-full text-white hover:bg-white/10 transition-colors"
      >
        <X size={24} weight="bold" aria-hidden="true" />
      </button>
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={src}
        alt={alt}
        // Unlike the screencast lightbox, a click on the picture closes as well.
        onClick={onClose}
        className="max-h-full max-w-full object-contain rounded-lg shadow-2xl cursor-zoom-out"
      />
    </div>,
    document.body,
  );
}

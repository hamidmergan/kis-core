"use client";

import { useTranslations } from "next-intl";
import { useEffect } from "react";

interface FolienGrossbildProps {
  index: number;
  total: number;
  previewUrl: string | null;
  onClose: () => void;
  onIndexChange: (index: number) => void;
}

/** The slide at full size over a dark backdrop, the same view the screencast uses. */
export default function FolienGrossbild({ index, total, previewUrl, onClose, onIndexChange }: FolienGrossbildProps) {
  const t = useTranslations("tools.praesentation.slides");
  const tCommon = useTranslations("tools.praesentation.common");

  useEffect(() => {
    function handler(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 bg-black/80 z-50 flex items-center justify-center px-4 pb-4 pt-[7rem]"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-label={t("slideLabel", { n: index + 1 })}
    >
      {/* Height runs out before width on a wide window, so the frame follows the 16:9 height cap. The top padding keeps the close cross clear of the page header. */}
      <div
        className="relative"
        style={{ width: "min(100%, 72rem, calc((100dvh - 13.25rem) * 16 / 9))" }}
        onClick={(e) => e.stopPropagation()}
      >
        <button
          type="button"
          onClick={onClose}
          className="absolute -top-10 right-0 text-white hover:text-border transition-colors"
          aria-label={tCommon("close")}
        >
          <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
        <p className="text-white text-sm text-center mb-2">
          {t("previewTitle", { n: index + 1, total })}
        </p>
        {previewUrl ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={previewUrl}
            alt={t("slideLabel", { n: index + 1 })}
            className="w-full max-h-[calc(100dvh-13.25rem)] object-contain rounded-lg shadow-2xl"
          />
        ) : (
          <p className="text-white/70 text-sm text-center py-16">{t("noPreview")}</p>
        )}
        <div className="flex justify-center gap-4 mt-4">
          <button
            type="button"
            onClick={() => onIndexChange(Math.max(0, index - 1))}
            disabled={index === 0}
            className="px-4 py-2 text-sm text-white border border-white/30 rounded-md hover:bg-white/10 transition-colors disabled:opacity-30"
          >
            {t("prev")}
          </button>
          <button
            type="button"
            onClick={() => onIndexChange(Math.min(total - 1, index + 1))}
            disabled={index === total - 1}
            className="px-4 py-2 text-sm text-white border border-white/30 rounded-md hover:bg-white/10 transition-colors disabled:opacity-30"
          >
            {t("next")}
          </button>
        </div>
      </div>
    </div>
  );
}

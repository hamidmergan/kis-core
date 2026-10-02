"use client";

import { useRef, useState } from "react";
import { useTranslations } from "next-intl";
import Modal from "@/components/ui/Modal";
import { useText2 } from "@/lib/event/useText2";
import type { Station } from "@/lib/event/types";
import PosterSvg, { useStationQr } from "./PosterSvg";
import { exportPosterPng, type PrintSize } from "./posterExport";
import { BTN_SECONDARY } from "./fields";

interface Props {
  station: Station;
  onClose: () => void;
  onPrint: (size: PrintSize) => void;
}

/** Poster preview for one stand with PNG download and the A5 and A4 print routes. */
export default function StationQr({ station, onClose, onPrint }: Props) {
  const t = useTranslations("eventAdmin.poster");
  const text = useText2();
  const art = useStationQr(station.id);
  const svgRef = useRef<SVGSVGElement>(null);
  const [busy, setBusy] = useState(false);

  const download = async () => {
    if (!svgRef.current) return;
    setBusy(true);
    try {
      await exportPosterPng(svgRef.current, `poster-${station.id}.png`);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal
      open
      onClose={onClose}
      title={t("title", { station: text(station.name) })}
      size="sm"
      footer={
        <div className="grid grid-cols-3 gap-2 w-full">
          {(["A5", "A4"] as const).map((size) => (
            <button
              key={size}
              type="button"
              onClick={() => onPrint(size)}
              disabled={!art}
              className={`${BTN_SECONDARY} w-full`}
              data-testid={`poster-${size.toLowerCase()}`}
            >
              {t(size === "A5" ? "a5" : "a4")}
            </button>
          ))}
          <button
            type="button"
            onClick={() => void download()}
            disabled={!art || busy}
            className="w-full px-4 py-2 text-sm btn-primary rounded-md disabled:opacity-50"
            data-testid="poster-png"
          >
            {t("png")}
          </button>
        </div>
      }
    >
      <div className="flex flex-col items-center gap-3">
        <PosterSvg
          ref={svgRef}
          station={station}
          art={art}
          className="w-full max-w-xs h-auto rounded-md border border-border shadow-sm"
        />
      </div>
    </Modal>
  );
}

"use client";

import { useRef, useState } from "react";
import { useTranslations } from "next-intl";
import Modal from "@/components/ui/Modal";
import { useText2 } from "../../../_lib/useText2";
import type { Station } from "../../../_lib/types";
import PosterSvg, { useStationQr } from "./PosterSvg";
import { exportPosterPng } from "./posterExport";
import { BTN_SECONDARY } from "./fields";

interface Props {
  station: Station;
  masterCode: string;
  onClose: () => void;
  onPrint: () => void;
}

/** Poster preview for one stand with PNG download and the A5 print route. */
export default function StationQr({ station, masterCode, onClose, onPrint }: Props) {
  const t = useTranslations("mockup.admin.poster");
  const tc = useTranslations("mockup.common");
  const text = useText2();
  const qr = useStationQr(station.id);
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
        <div className="flex flex-wrap justify-end gap-2">
          <button type="button" onClick={onClose} className="btn-cancel px-4 py-2 text-sm btn-secondary rounded-lg">
            {tc("close")}
          </button>
          <button type="button" onClick={onPrint} disabled={!qr} className={BTN_SECONDARY} data-testid="poster-pdf">
            {t("pdf")}
          </button>
          <button
            type="button"
            onClick={() => void download()}
            disabled={!qr || busy}
            className="px-4 py-2 text-sm btn-primary rounded-lg disabled:opacity-50"
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
          qr={qr}
          masterCode={masterCode}
          className="w-full max-w-xs h-auto rounded-md border border-border shadow-sm"
        />
        <p className="text-xs text-muted text-center max-w-xs">{t("printHint")}</p>
      </div>
    </Modal>
  );
}

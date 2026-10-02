"use client";

import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import type { Station } from "../../../_lib/types";
import PosterSvg, { useStationQr } from "./PosterSvg";

const SHEET = "mockup-poster-sheet";

function PrintPoster({ station, masterCode, last, onReady }: {
  station: Station;
  masterCode: string;
  last: boolean;
  onReady: (id: string) => void;
}) {
  const qr = useStationQr(station.id);
  useEffect(() => {
    if (qr) onReady(station.id);
  }, [qr, station.id, onReady]);
  return (
    <div style={{ breakAfter: last ? "auto" : "page" }}>
      <PosterSvg station={station} qr={qr} masterCode={masterCode} className="block w-full h-auto" />
    </div>
  );
}

/** One poster per A5 page, opens the print dialog once every QR code is drawn. */
export default function PosterPrintSheet({ stations, masterCode, onDone }: {
  stations: Station[];
  masterCode: string;
  onDone: () => void;
}) {
  const [ready, setReady] = useState<Record<string, true>>({});
  const printed = useRef(false);
  const allReady = stations.length > 0 && stations.every((s) => ready[s.id]);

  useEffect(() => {
    if (!allReady || printed.current) return;
    printed.current = true;
    const finish = () => onDone();
    window.addEventListener("afterprint", finish, { once: true });
    const timer = window.setTimeout(() => window.print(), 150);
    return () => {
      window.clearTimeout(timer);
      window.removeEventListener("afterprint", finish);
    };
  }, [allReady, onDone]);

  if (typeof document === "undefined") return null;
  return createPortal(
    <div className={`${SHEET} hidden print:block`} data-testid="poster-sheet">
      <style>{`
        @page { size: A5; margin: 10mm; }
        @media print {
          body > :not(.${SHEET}) { display: none !important; }
          .${SHEET} { display: block !important; }
        }
      `}</style>
      {stations.map((s, i) => (
        <PrintPoster
          key={s.id}
          station={s}
          masterCode={masterCode}
          last={i === stations.length - 1}
          onReady={(id) => setReady((r) => (r[id] ? r : { ...r, [id]: true }))}
        />
      ))}
    </div>,
    document.body,
  );
}

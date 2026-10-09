"use client";

import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import type { Station } from "@/lib/event/types";
import PosterSvg, { useStationQr } from "./PosterSvg";

const SHEET = "event-poster-sheet";

function PrintPoster({ station, last, onReady }: {
  station: Station;
  last: boolean;
  onReady: (id: string) => void;
}) {
  const art = useStationQr(station.id);
  useEffect(() => {
    if (art) onReady(station.id);
  }, [art, station.id, onReady]);
  return (
    <div style={{ breakAfter: last ? "auto" : "page", padding: "10mm" }}>
      <PosterSvg station={station} art={art} className="block w-full h-auto" />
    </div>
  );
}

/** One A4 poster per page, opens the print dialog once every QR code is drawn. */
export default function PosterPrintSheet({ stations, onDone }: {
  stations: Station[];
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
        @page { size: A4; margin: 0; }
        @media print {
          body > :not(.${SHEET}) { display: none !important; }
          .${SHEET} { display: block !important; }
        }
      `}</style>
      {stations.map((s, i) => (
        <PrintPoster
          key={s.id}
          station={s}
          last={i === stations.length - 1}
          onReady={(id) => setReady((r) => (r[id] ? r : { ...r, [id]: true }))}
        />
      ))}
    </div>,
    document.body,
  );
}

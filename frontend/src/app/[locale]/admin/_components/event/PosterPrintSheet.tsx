"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";
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

/** Portal that hides the page, prints once `ready` turns true and reports back through `onDone`. */
export function PrintShell({ ready, onDone, children }: {
  ready: boolean;
  onDone: () => void;
  children: ReactNode;
}) {
  const printed = useRef(false);

  useEffect(() => {
    if (!ready || printed.current) return;
    const finish = () => onDone();
    window.addEventListener("afterprint", finish, { once: true });
    // Marked inside the timer so a StrictMode remount, which clears it, still prints.
    const timer = window.setTimeout(() => {
      printed.current = true;
      window.print();
    }, 150);
    return () => {
      window.clearTimeout(timer);
      window.removeEventListener("afterprint", finish);
    };
  }, [ready, onDone]);

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
      {children}
    </div>,
    document.body,
  );
}

/** One A4 poster per page, opens the print dialog once every QR code is drawn. */
export default function PosterPrintSheet({ stations, onDone }: {
  stations: Station[];
  onDone: () => void;
}) {
  const [ready, setReady] = useState<Record<string, true>>({});
  const allReady = stations.length > 0 && stations.every((s) => ready[s.id]);
  return (
    <PrintShell ready={allReady} onDone={onDone}>
      {stations.map((s, i) => (
        <PrintPoster
          key={s.id}
          station={s}
          last={i === stations.length - 1}
          onReady={(id) => setReady((r) => (r[id] ? r : { ...r, [id]: true }))}
        />
      ))}
    </PrintShell>
  );
}

"use client";

import { useCallback, useState } from "react";
import { useEventConfig } from "@/lib/event/adminStore";
import StationsCard from "./StationsCard";
import StationQr from "./StationQr";
import PosterPrintSheet from "./PosterPrintSheet";
import type { PrintSize } from "./posterExport";

type PrintJob = { ids: string[]; size: PrintSize; nonce: number };

/** Stands, plus the poster modal and the print sheet they open. */
export default function StationsPane() {
  const [config] = useEventConfig();
  const [qrId, setQrId] = useState<string | null>(null);
  const [job, setJob] = useState<PrintJob | null>(null);
  // Stable so the print sheet's effect does not restart on every render.
  const clearJob = useCallback(() => setJob(null), []);
  const qrStation = qrId ? config.stations.find((s) => s.id === qrId) : undefined;
  const printStations = job ? config.stations.filter((s) => job.ids.includes(s.id)) : [];

  return (
    <div className="flex flex-col gap-4">
      <StationsCard
        onQr={setQrId}
        onPrintAll={(size) => setJob({ ids: config.stations.map((s) => s.id), size, nonce: Date.now() })}
      />
      {qrStation && (
        <StationQr
          station={qrStation}
          onClose={() => setQrId(null)}
          onPrint={(size) => setJob({ ids: [qrStation.id], size, nonce: Date.now() })}
        />
      )}
      {job && printStations.length > 0 && (
        <PosterPrintSheet
          key={job.nonce}
          stations={printStations}
          size={job.size}
          onDone={clearJob}
        />
      )}
    </div>
  );
}

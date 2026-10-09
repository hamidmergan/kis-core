"use client";

import { useCallback, useState } from "react";
import { useEventConfig } from "@/lib/event/adminStore";
import StationsCard from "./StationsCard";
import StationQr from "./StationQr";
import PosterPrintSheet from "./PosterPrintSheet";

type PrintJob = { ids: string[]; nonce: number };

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
      <StationsCard onQr={setQrId} />
      {qrStation && (
        <StationQr
          station={qrStation}
          onClose={() => setQrId(null)}
          onPrint={() => setJob({ ids: [qrStation.id], nonce: Date.now() })}
        />
      )}
      {job && printStations.length > 0 && (
        <PosterPrintSheet key={job.nonce} stations={printStations} onDone={clearJob} />
      )}
    </div>
  );
}

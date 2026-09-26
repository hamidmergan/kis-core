"use client";

import { useCallback, useEffect, useState } from "react";
import { parseDetail } from "@/lib/api";
import { hatMaterial, KEIN_MATERIAL, type MaterialWahl } from "../_components/ZusatzMaterial";

/** The extra material of one job: what is picked, what the job already carries, and the way in. */
export function useZusatzMaterial(jobUuid: string, aktiv: boolean, fallback: string) {
  const [wahl, setWahl] = useState<MaterialWahl>(KEIN_MATERIAL);
  const [hinterlegt, setHinterlegt] = useState<string[]>([]);
  const [entfernen, setEntfernen] = useState(false);
  const [bereit, setBereit] = useState(true);
  const [laedt, setLaedt] = useState(false);
  const [fehler, setFehler] = useState("");

  // Whoever comes back to the step sees what the job already reads from.
  useEffect(() => {
    if (!aktiv || !jobUuid) return;
    fetch(`/api/screencast/${jobUuid}/material`, { credentials: "include" })
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => d && setHinterlegt(Array.isArray(d.files) ? d.files : []))
      .catch(() => {});
  }, [aktiv, jobUuid]);

  const waehlen = useCallback((w: MaterialWahl) => {
    setWahl(w);
    setFehler("");
  }, []);

  /** Brings the job in line with the choice, false when the material was refused. */
  const abgleichen = useCallback(async (): Promise<boolean> => {
    if (!jobUuid) return true;
    const neu = hatMaterial(wahl);
    if (!neu && !entfernen) return true;
    setLaedt(true);
    setFehler("");
    try {
      let res: Response;
      if (neu) {
        const body = new FormData();
        body.append("mode", wahl.mode);
        if (wahl.mode === "files") wahl.files.forEach((f) => body.append("files", f));
        else {
          body.append("workspace_uuid", wahl.moduleId);
          body.append("source_uuids", JSON.stringify(wahl.sourceIds));
        }
        res = await fetch(`/api/screencast/${jobUuid}/material`, { method: "POST", body, credentials: "include" });
      } else {
        res = await fetch(`/api/screencast/${jobUuid}/material`, { method: "DELETE", credentials: "include" });
      }
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        setFehler(parseDetail(data.detail, fallback));
        return false;
      }
      setHinterlegt(Array.isArray(data.files) ? data.files : []);
      setWahl(KEIN_MATERIAL);
      setEntfernen(false);
      return true;
    } catch {
      setFehler(fallback);
      return false;
    } finally {
      setLaedt(false);
    }
  }, [jobUuid, wahl, entfernen, fallback]);

  const hinterlegtEntfernen = useCallback(() => {
    setHinterlegt([]);
    setEntfernen(true);
  }, []);

  const reset = useCallback(() => {
    setWahl(KEIN_MATERIAL);
    setHinterlegt([]);
    setEntfernen(false);
    setFehler("");
  }, []);

  return { wahl, waehlen, hinterlegt, hinterlegtEntfernen, bereit, setBereit, laedt, fehler, abgleichen, reset };
}

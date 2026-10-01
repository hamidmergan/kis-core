"use client";

import { useEffect, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { Trash } from "@phosphor-icons/react";
import IconButton from "@/components/ui/IconButton";
import Modal from "@/components/ui/Modal";
import { backendApi } from "@/lib/api";
import { formatDate } from "@/lib/format";
import { notifyJobsChanged } from "@/lib/jobs-events";

/** What a result was made with, as the backend keeps it next to the result. */
export interface ErgebnisAngaben {
  anbieter?: string;
  ziel?: string;
  glossar?: boolean;
  stimme?: string;
  format?: string;
  vorlage?: string;
}

interface Auftrag {
  angaben: ErgebnisAngaben;
  erstellt: string | null;
  datei: string | null;
}

/** Reads the info of one finished job, older jobs simply come without angaben. */
export function useErgebnisAngaben(jobUuid: string | null): Auftrag | null {
  const [auftrag, setAuftrag] = useState<Auftrag | null>(null);
  useEffect(() => {
    setAuftrag(null);
    if (!jobUuid) return;
    let abgelaufen = false;
    backendApi.fetch(`/jobs/${jobUuid}`)
      .then((r) => (r.ok ? r.json() : null))
      .then((job) => {
        if (abgelaufen || !job) return;
        setAuftrag({ angaben: job.meta?.angaben ?? {}, erstellt: job.created_at ?? null, datei: job.original_filename ?? null });
      })
      .catch(() => { /* The info is a bonus, the result stands without it. */ });
    return () => { abgelaufen = true; };
  }, [jobUuid]);
  return auftrag;
}

/** The info rows under a result and the way to delete it, the same on every tool page. */
export default function ErgebnisInfo({ jobUuid, auftrag, zeilen, onGeloescht }: {
  jobUuid: string;
  auftrag: Auftrag | null;
  /** Tool-specific rows, an empty value leaves its row out. */
  zeilen: { label: string; wert?: string | null }[];
  onGeloescht: () => void;
}) {
  const t = useTranslations("common.result");
  const locale = useLocale();
  const [fragt, setFragt] = useState(false);
  const [loescht, setLoescht] = useState(false);
  const [fehler, setFehler] = useState("");

  const alle = [
    ...zeilen,
    { label: t("created"), wert: auftrag?.erstellt ? formatDate(auftrag.erstellt, locale) : null },
  ].filter((z) => z.wert);

  const loeschen = async () => {
    setLoescht(true);
    setFehler("");
    try {
      const r = await backendApi.fetch(`/jobs/${jobUuid}`, { method: "DELETE" });
      if (!r.ok) throw new Error();
      notifyJobsChanged();
      // A deleted job must not come back from the address on reload.
      const adresse = new URL(window.location.href);
      if (adresse.searchParams.has("job")) {
        adresse.searchParams.delete("job");
        window.history.replaceState(null, "", adresse.pathname + adresse.search);
      }
      setFragt(false);
      onGeloescht();
    } catch {
      setFehler(t("deleteFailed"));
    } finally {
      setLoescht(false);
    }
  };

  return (
    <div className="flex items-start justify-between gap-3 rounded-md border border-border-soft bg-background px-3 py-2">
      <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5 text-xs min-w-0">
        {alle.map((z) => (
          <div key={z.label} className="contents">
            <dt className="text-muted">{z.label}</dt>
            <dd className="text-foreground-soft truncate">{z.wert}</dd>
          </div>
        ))}
      </dl>
      <IconButton size="sm" aria-label={t("delete")} title={t("delete")} onClick={() => setFragt(true)}>
        <Trash size={14} />
      </IconButton>
      {fragt && (
        <Modal open onClose={() => setFragt(false)} size="sm" title={t("deleteTitle")}
          footer={<>
            <button type="button" onClick={() => setFragt(false)} disabled={loescht}
              className="btn-cancel px-4 py-2 text-sm btn-secondary rounded-lg disabled:opacity-50">{t("cancel")}</button>
            <button type="button" onClick={loeschen} disabled={loescht}
              className="px-4 py-2 text-sm btn-danger rounded-lg disabled:opacity-50">{loescht ? "..." : t("confirm")}</button>
          </>}>
          {auftrag?.datei && <p className="text-sm font-medium break-words">{auftrag.datei}</p>}
          <p className="text-sm text-muted mt-2">{t("deleteWarning")}</p>
          {fehler && <p className="text-sm text-error mt-2" role="alert">{fehler}</p>}
        </Modal>
      )}
    </div>
  );
}

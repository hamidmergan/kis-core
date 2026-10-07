"use client";

import { useEffect, useState, type ReactNode } from "react";
import { useLocale, useTranslations } from "next-intl";
import { Info, Trash } from "@phosphor-icons/react";
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
  sprache?: string;
  format?: string;
  vorlage?: string;
  anweisung?: string;
  material?: string;
  /** Who speaks in a podcast, the role as its key. */
  besetzung?: { name: string; rolle: string; stimme: string }[];
  /** A picture's prompt and settings, the task and question of an answer about it. */
  prompt?: string;
  stil?: string;
  qualitaet?: string;
  groesse?: string;
  aufgabe?: string;
  frage?: string;
  /** Who wrote the text when another provider speaks or draws, and who drew the pictures. */
  textanbieter?: string;
  bildanbieter?: string;
  bildstil?: string;
}

export interface Auftrag {
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
        setAuftrag({ angaben: job.angaben ?? {}, erstellt: job.created_at ?? null, datei: job.original_filename ?? null });
      })
      .catch(() => { /* The info is a bonus, the result stands without it. */ });
    return () => { abgelaufen = true; };
  }, [jobUuid]);
  return auftrag;
}

/** An info icon next to the result, a click shows in a modal what it was made with. */
export function ErgebnisInfoKnopf({ auftrag, zeilen }: {
  auftrag: Auftrag | null;
  /** Tool-specific rows, an empty value leaves its row out. */
  zeilen: { label: string; wert?: ReactNode }[];
}) {
  const t = useTranslations("common.result");
  const locale = useLocale();
  const [offen, setOffen] = useState(false);

  const alle = [
    ...zeilen,
    { label: t("created"), wert: auftrag?.erstellt ? formatDate(auftrag.erstellt, locale) : null },
  ].filter((z) => z.wert);

  if (!alle.length) return null;
  return (
    <>
      <IconButton size="sm" aria-label={t("info")} title={t("info")} onClick={() => setOffen(true)}>
        <Info size={16} />
      </IconButton>
      {offen && (
        <Modal open onClose={() => setOffen(false)} size="sm" title={t("info")}>
          <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 text-sm text-left">
            {alle.map((z) => (
              <div key={z.label} className="contents">
                <dt className="text-muted">{z.label}</dt>
                <dd className="text-foreground break-words whitespace-pre-wrap min-w-0">{z.wert}</dd>
              </div>
            ))}
          </dl>
        </Modal>
      )}
    </>
  );
}

/** Deletes the result and its job after one question, then the page starts fresh. */
export function ErgebnisLoeschenKnopf({ jobUuid, auftrag, onGeloescht }: {
  jobUuid: string;
  auftrag: Auftrag | null;
  onGeloescht: () => void;
}) {
  const t = useTranslations("common.result");
  const [fragt, setFragt] = useState(false);
  const [loescht, setLoescht] = useState(false);
  const [fehler, setFehler] = useState("");

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
    <>
      <button type="button" onClick={() => setFragt(true)}
        className="px-4 py-2 text-sm text-foreground-soft border border-border rounded-md btn-ghost focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-kb transition-colors flex items-center gap-2">
        <Trash size={14} aria-hidden="true" />
        {t("delete")}
      </button>
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
    </>
  );
}

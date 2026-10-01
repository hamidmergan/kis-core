"use client";

import { PencilSimple, Plus, Trash } from "@phosphor-icons/react";
import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import HelpTooltip from "@/components/ui/HelpTooltip";
import IconButton from "@/components/ui/IconButton";
import Spinner from "@/components/ui/Spinner";
import { deleteVorlage, listVorlagen, vorlagePreviewUrl } from "../_api";
import type { Vorlage } from "../_types";
import VorlageBearbeiten from "./VorlageBearbeiten";
import VorlageHochladen from "./VorlageHochladen";

// Empty placeholder boxes, the way PowerPoint's own slide master view shows them without content.
const FOLIENMASTER_SKIZZE = (
  <svg viewBox="0 0 160 90" className="w-full" aria-hidden="true">
    <rect x="1" y="1" width="158" height="88" rx="4" fill="var(--surface)" stroke="var(--border)" strokeWidth="2" />
    <rect x="10" y="10" width="140" height="16" rx="2" fill="none" stroke="var(--muted)" strokeWidth="1.5" strokeDasharray="4 3" />
    <rect x="10" y="34" width="84" height="46" rx="2" fill="none" stroke="var(--muted)" strokeWidth="1.5" strokeDasharray="4 3" />
    <rect x="102" y="34" width="48" height="46" rx="2" fill="none" stroke="var(--muted)" strokeWidth="1.5" strokeDasharray="4 3" />
    <circle cx="117" cy="51" r="4" fill="none" stroke="var(--muted)" strokeWidth="1.5" />
    <path d="M107 70l10-10 7 7 6-6 10 10" fill="none" stroke="var(--muted)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

interface VorlagenWahlProps {
  templateId: string;
  onTemplate: (id: string) => void;
  /** The chosen template as loaded, so the page can offer its picture style. */
  onVorlage: (v: Vorlage | undefined) => void;
  /** Shows only the chosen template, without upload, edit or delete, as the demo needs it. */
  nurGewaehlte?: boolean;
}

/** The system template and the person's own ones as tiles, the cover layout as the picture. */
export default function VorlagenWahl({ templateId, onTemplate, onVorlage, nurGewaehlte = false }: VorlagenWahlProps) {
  const t = useTranslations("tools.praesentation.content");
  const [vorlagen, setVorlagen] = useState<Vorlage[] | null>(null);
  const [hochladen, setHochladen] = useState(false);
  const [bearbeiten, setBearbeiten] = useState<Vorlage | null>(null);

  const laden = () => listVorlagen().then(setVorlagen).catch(() => setVorlagen([]));
  useEffect(() => {
    laden();
  }, []);

  useEffect(() => {
    if (vorlagen) onVorlage(vorlagen.find((v) => v.id === templateId));
  }, [vorlagen, templateId, onVorlage]);

  const loeschen = async (id: string) => {
    await deleteVorlage(id).catch(() => undefined);
    if (templateId === id) onTemplate("thl");
    laden();
  };

  if (vorlagen === null) return <Spinner size="sm" className="my-4" />;

  return (
    <div className="mt-6">
      <div className="flex items-center gap-1.5 mb-2">
        <p className="text-sm font-medium">{t("templateLabel")}</p>
        <HelpTooltip text={t("templateHelp")} image={FOLIENMASTER_SKIZZE} />
      </div>
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-3" role="radiogroup" aria-label={t("templateLabel")}>
        {vorlagen.filter((v) => !nurGewaehlte || v.id === templateId).map((v) => {
          const aktiv = v.id === templateId;
          return (
            <div key={v.id} className="relative">
              <button
                type="button"
                role="radio"
                aria-checked={aktiv}
                onClick={() => onTemplate(v.id)}
                className={`w-full text-left rounded-xl border-2 transition-colors p-2 ${aktiv ? "border-kb" : "border-border hover:border-kb"}`}
              >
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={vorlagePreviewUrl(v.id)} alt="" className="w-full aspect-video object-cover rounded-md bg-surface" />
                <p className="text-sm font-medium mt-2 truncate">{v.name}</p>
                <p className="text-xs text-muted">
                  {v.hasImages ? t("templateWithImages") : t("templateWithoutImages")}
                </p>
              </button>
              {!v.system && !nurGewaehlte && (
                <>
                  <IconButton size="sm" aria-label={t("editTemplate", { name: v.name })}
                              className="absolute top-2 right-9" onClick={() => setBearbeiten(v)}>
                    <PencilSimple className="w-3 h-3" />
                  </IconButton>
                  <IconButton size="sm" aria-label={t("deleteTemplate", { name: v.name })}
                              className="absolute top-2 right-2" onClick={() => loeschen(v.id)}>
                    <Trash className="w-3 h-3" />
                  </IconButton>
                </>
              )}
            </div>
          );
        })}
        {!nurGewaehlte && <button
          type="button"
          onClick={() => setHochladen(true)}
          className="rounded-xl border-2 border-dashed border-border hover:border-kb transition-colors p-4 flex flex-col items-center justify-center gap-2 text-sm text-foreground-soft"
        >
          <Plus className="w-5 h-5" />
          {t("uploadTemplate")}
        </button>}
      </div>
      {hochladen && (
        <VorlageHochladen
          onClose={() => setHochladen(false)}
          onUploaded={(v) => {
            setHochladen(false);
            onTemplate(v.id);
            laden();
          }}
        />
      )}
      {bearbeiten && (
        <VorlageBearbeiten
          vorlage={bearbeiten}
          onClose={() => setBearbeiten(null)}
          onSaved={() => {
            setBearbeiten(null);
            laden();
          }}
        />
      )}
    </div>
  );
}

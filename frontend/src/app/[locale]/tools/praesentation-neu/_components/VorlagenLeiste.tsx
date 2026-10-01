"use client";

import { PencilSimple, Plus, Trash } from "@phosphor-icons/react";
import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import HelpTooltip from "@/components/ui/HelpTooltip";
import IconButton from "@/components/ui/IconButton";
import Spinner from "@/components/ui/Spinner";
import { deleteVorlage, listVorlagen, vorlagePreviewUrl } from "../../praesentation/_api";
import VorlageBearbeiten from "../../praesentation/_components/VorlageBearbeiten";
import VorlageHochladen from "../../praesentation/_components/VorlageHochladen";
import type { Vorlage } from "../../praesentation/_types";

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

interface Props {
  templateId: string;
  onTemplate: (id: string) => void;
  /** The chosen template as loaded, for the stage and the picture style. */
  onVorlage: (v: Vorlage | undefined) => void;
}

/** The templates as small tiles, a carousel on the phone and a grid in the form card on the desktop. */
export default function VorlagenLeiste({ templateId, onTemplate, onVorlage }: Props) {
  const t = useTranslations("tools.praesentation.content");
  const [vorlagen, setVorlagen] = useState<Vorlage[] | null>(null);
  const [hochladen, setHochladen] = useState(false);
  const [bearbeiten, setBearbeiten] = useState<Vorlage | null>(null);

  const laden = () => listVorlagen().then(setVorlagen).catch(() => setVorlagen([]));
  useEffect(() => {
    laden();
  }, []);

  const aktiv = vorlagen?.find((v) => v.id === templateId);
  useEffect(() => {
    if (vorlagen) onVorlage(aktiv);
  }, [vorlagen, aktiv, onVorlage]);

  const loeschen = async (id: string) => {
    await deleteVorlage(id).catch(() => undefined);
    if (templateId === id) onTemplate("thl");
    laden();
  };

  if (vorlagen === null) return <Spinner size="sm" className="my-4" />;

  const kachel = "shrink-0 w-36 snap-start lg:w-auto";

  return (
    <div>
      <div className="flex items-center gap-1.5 mb-2">
        <p className="text-sm font-medium">{t("templateLabel")}</p>
        <HelpTooltip text={t("templateHelp")} image={FOLIENMASTER_SKIZZE} />
      </div>
      <div
        className="flex gap-2.5 overflow-x-auto snap-x scrollbar-hide pb-1 lg:grid lg:grid-cols-3 lg:overflow-visible"
        role="radiogroup"
        aria-label={t("templateLabel")}
      >
        {vorlagen.map((v) => {
          const gewaehlt = v.id === templateId;
          return (
            <div key={v.id} className={`relative ${kachel}`}>
              <button
                type="button"
                role="radio"
                aria-checked={gewaehlt}
                onClick={() => onTemplate(v.id)}
                className={`w-full text-left rounded-lg border-2 transition-colors p-1 ${gewaehlt ? "border-kb" : "border-border hover:border-kb"}`}
              >
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={vorlagePreviewUrl(v.id)} alt="" className="w-full aspect-video object-cover rounded bg-surface" />
                <p className={`text-xs mt-1 px-0.5 truncate ${gewaehlt ? "text-kb font-semibold" : "text-muted"}`}>{v.name}</p>
              </button>
              {!v.system && (
                <span className="absolute top-2 right-2 flex gap-1">
                  <IconButton size="sm" aria-label={t("editTemplate", { name: v.name })} onClick={() => setBearbeiten(v)}>
                    <PencilSimple className="w-3 h-3" />
                  </IconButton>
                  <IconButton size="sm" aria-label={t("deleteTemplate", { name: v.name })} onClick={() => loeschen(v.id)}>
                    <Trash className="w-3 h-3" />
                  </IconButton>
                </span>
              )}
            </div>
          );
        })}
        <button
          type="button"
          onClick={() => setHochladen(true)}
          className={`${kachel} rounded-lg border-2 border-dashed border-border hover:border-kb transition-colors p-2 flex flex-col items-center justify-center gap-1 text-xs text-foreground-soft text-center`}
        >
          <Plus className="w-4 h-4" />
          {t("uploadTemplate")}
        </button>
      </div>
      {aktiv && (
        <p className="text-xs text-muted mt-1.5">{aktiv.hasImages ? t("templateWithImages") : t("templateWithoutImages")}</p>
      )}
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

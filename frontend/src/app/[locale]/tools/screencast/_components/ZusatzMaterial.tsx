"use client";

import { useEffect, useRef, useState, type DragEvent } from "react";
import { useFormatter, useTranslations } from "next-intl";
import { X } from "@phosphor-icons/react";
import Checkbox from "@/components/ui/Checkbox";
import { EmptyState } from "@/components/ui/EmptyState";
import IconButton from "@/components/ui/IconButton";
import Select from "@/components/ui/Select";
import Spinner from "@/components/ui/Spinner";
import Tabs from "@/components/ui/Tabs";
import MaterialGauge, { MeasureError, MeasureNote } from "@/components/tools/MaterialGauge";
import { useModules } from "@/hooks/useModules";
import { useMaterialMeasure } from "@/hooks/useMaterialMeasure";
import { MAX_MATERIAL_CHARS } from "@/lib/materialMeasure";

const ACCEPT = ".pdf,.docx,.pptx,.txt,.md";
/** Mirrors SCREENCAST_MAX_SOURCES in the backend. */
export const MAX_MATERIAL_DATEIEN = 10;

export type MaterialModus = "files" | "module";

export interface MaterialWahl {
  mode: MaterialModus;
  files: File[];
  moduleId: string;
  sourceIds: string[];
}

export const KEIN_MATERIAL: MaterialWahl = { mode: "files", files: [], moduleId: "", sourceIds: [] };

export function hatMaterial(w: MaterialWahl): boolean {
  return w.mode === "files" ? w.files.length > 0 : !!w.moduleId && w.sourceIds.length > 0;
}

interface Props {
  wahl: MaterialWahl;
  onWahl: (w: MaterialWahl) => void;
  canUseModules: boolean;
  /** File names the job already carries from an earlier step. */
  hinterlegt: string[];
  onHinterlegtEntfernen: () => void;
  fehler: string;
  /** Tells the step whether the picked material may be used. */
  onBereit: (bereit: boolean) => void;
  demo?: boolean;
}

/** Extra documents whose matching passages flow into the scripts of the slides. */
export default function ZusatzMaterial({ wahl, onWahl, canUseModules, hinterlegt, onHinterlegtEntfernen,
                                         fehler, onBereit, demo = false }: Props) {
  const t = useTranslations("tools.screencast.material");
  const tDemo = useTranslations("tools.screencastDemo");
  const tCommon = useTranslations("common");
  const format = useFormatter();
  const fileRef = useRef<HTMLInputElement>(null);
  const [dragOver, setDragOver] = useState(false);
  const mode: MaterialModus = canUseModules || wahl.mode !== "module" ? wahl.mode : "files";
  const { modules, sources } = useModules(!demo && mode === "module" ? wahl.moduleId : "");
  const messung = useMaterialMeasure("screencast", demo ? "" : mode, wahl.files, wahl.moduleId, wahl.sourceIds);
  const zuViele = wahl.files.length > MAX_MATERIAL_DATEIEN;
  const bereit = !hatMaterial({ ...wahl, mode }) || (messung.ready && !zuViele);

  useEffect(() => onBereit(bereit), [bereit, onBereit]);

  const kopf = (
    <>
      <h3 className="text-sm font-medium text-foreground-soft">{t("titel")}</h3>
      <p className="mt-1 mb-3 text-xs text-muted">
        {t("hinweis", { max: MAX_MATERIAL_DATEIEN, chars: format.number(messung.max ?? MAX_MATERIAL_CHARS) })}
      </p>
    </>
  );

  if (demo) {
    return (
      <section className="mt-8">
        {kopf}
        <div className="flex flex-col items-center justify-center rounded-lg border-2 border-dashed border-border-soft bg-surface px-4 py-5 opacity-60 cursor-not-allowed">
          <p className="text-xs text-muted">{tDemo("keinHochladen")}</p>
        </div>
      </section>
    );
  }

  const addFiles = (list: FileList | null) => {
    if (!list) return;
    const dabei = new Set(wahl.files.map((f) => f.name));
    onWahl({ ...wahl, files: [...wahl.files, ...Array.from(list).filter((f) => !dabei.has(f.name))] });
  };
  const onDrop = (e: DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    addFiles(e.dataTransfer.files);
  };
  const voll = wahl.sourceIds.length >= MAX_MATERIAL_DATEIEN;
  const toggleSource = (uuid: string) => {
    const set = new Set(wahl.sourceIds);
    if (set.has(uuid)) set.delete(uuid);
    else if (!voll) set.add(uuid);
    onWahl({ ...wahl, sourceIds: [...set] });
  };

  return (
    <section className="mt-8">
      {kopf}

      {hinterlegt.length > 0 && !hatMaterial({ ...wahl, mode }) && (
        <div className="mb-3 flex items-center justify-between gap-3 rounded-lg bg-surface px-3 py-2 text-sm text-foreground-soft">
          <span className="min-w-0 truncate">{t("hinterlegt", { namen: hinterlegt.join(", ") })}</span>
          <button
            type="button"
            onClick={onHinterlegtEntfernen}
            className="shrink-0 rounded-sm px-1 py-0.5 text-sm font-medium text-kb hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-kb"
          >
            {t("entfernen")}
          </button>
        </div>
      )}

      {canUseModules && (
        <Tabs<MaterialModus>
          className="mb-3"
          active={mode}
          onChange={(next) => onWahl({ ...wahl, mode: next })}
          items={[
            { key: "files", label: t("tabDateien") },
            { key: "module", label: "Workspace" },
          ]}
        />
      )}

      {mode === "files" && (
        <>
          <div
            onDragOver={(e) => {
              e.preventDefault();
              setDragOver(true);
            }}
            onDragLeave={(e) => {
              e.preventDefault();
              setDragOver(false);
            }}
            onDrop={onDrop}
            onClick={() => fileRef.current?.click()}
            className={`mb-3 flex flex-col items-center justify-center rounded-lg border-2 border-dashed px-4 py-6 transition-colors cursor-pointer ${
              dragOver ? "border-kb bg-kb/5" : "border-border hover:border-kb"
            }`}
          >
            <input
              ref={fileRef}
              type="file"
              multiple
              accept={ACCEPT}
              className="hidden"
              aria-label={tCommon("fileSelectAria")}
              onChange={(e) => {
                addFiles(e.target.files);
                e.target.value = "";
              }}
            />
            <p className="text-sm text-foreground-soft">
              {t("dropOrBrowse")} <span className="text-kb font-medium">{t("browse")}</span>
            </p>
            <p className="text-xs text-muted-soft mt-1">{t("filesHint")}</p>
          </div>
          {wahl.files.length > 0 && (
            <>
              <MaterialGauge bilanz={messung} max={messung.max} />
              <ul className="space-y-2">
                {wahl.files.map((datei) => (
                  <li key={datei.name} className="rounded-lg border border-border-soft px-3 py-2 text-sm">
                    <div className="flex items-center justify-between gap-3">
                      <span className="truncate">{datei.name}</span>
                      <span className="flex items-center gap-2 shrink-0">
                        <MeasureNote messung={messung.forFile(datei)} />
                        <IconButton
                          size="sm"
                          aria-label={t("removeFile", { name: datei.name })}
                          onClick={() => onWahl({ ...wahl, files: wahl.files.filter((f) => f.name !== datei.name) })}
                        >
                          <X size={12} weight="bold" />
                        </IconButton>
                      </span>
                    </div>
                    <MeasureError messung={messung.forFile(datei)} />
                  </li>
                ))}
              </ul>
              {zuViele && (
                <p className="mt-2 text-xs text-error font-medium" role="alert">
                  {t("zuVieleDateien", { max: MAX_MATERIAL_DATEIEN })}
                </p>
              )}
            </>
          )}
        </>
      )}

      {mode === "module" && (
        modules === null ? (
          <Spinner className="justify-center py-6" />
        ) : modules.length === 0 ? (
          <EmptyState size="sm" text={t("noModules")} />
        ) : (
          <div className="space-y-4">
            <Select
              ariaLabel="Workspace"
              value={wahl.moduleId}
              onChange={(uuid) => onWahl({ ...wahl, moduleId: uuid, sourceIds: [] })}
              placeholder={tCommon("pleaseSelect")}
              options={modules.map((m) => ({ value: m.uuid, label: m.title }))}
            />
            {wahl.moduleId &&
              (sources === null ? (
                <Spinner className="justify-center py-6" />
              ) : sources.length === 0 ? (
                <EmptyState size="sm" text={t("noSources")} />
              ) : (
                <div>
                  {wahl.sourceIds.length > 0 && <MaterialGauge bilanz={messung} max={messung.max} />}
                  <ul className="space-y-2">
                    {sources.map((s) => (
                      <li key={s.uuid}>
                        <div className="flex items-center justify-between gap-3">
                          <Checkbox
                            checked={wahl.sourceIds.includes(s.uuid)}
                            disabled={voll && !wahl.sourceIds.includes(s.uuid)}
                            onChange={() => toggleSource(s.uuid)}
                            label={s.filename}
                            labelClassName="text-sm text-foreground"
                          />
                          {wahl.sourceIds.includes(s.uuid) && <MeasureNote messung={messung.forSource(s.uuid)} />}
                        </div>
                        {wahl.sourceIds.includes(s.uuid) && <MeasureError messung={messung.forSource(s.uuid)} />}
                      </li>
                    ))}
                  </ul>
                  <p className={`mt-2 text-xs ${voll ? "text-error font-medium" : "text-muted"}`}>
                    {t(voll ? "sourcesFull" : "sourcesHint", { max: MAX_MATERIAL_DATEIEN })}
                  </p>
                </div>
              ))}
          </div>
        )
      )}

      {fehler && (
        <p className="mt-3 rounded-lg border border-error-border bg-error-bg px-3 py-2 text-sm text-error" role="alert">
          {fehler}
        </p>
      )}
    </section>
  );
}

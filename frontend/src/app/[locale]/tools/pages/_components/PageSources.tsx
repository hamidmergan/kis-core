"use client";

import { useRef, useState } from "react";
import { useTranslations } from "next-intl";
import Checkbox from "@/components/ui/Checkbox";
import Select from "@/components/ui/Select";
import Spinner from "@/components/ui/Spinner";
import { EmptyState } from "@/components/ui/EmptyState";
import MaterialGauge, { MeasureError, MeasureNote } from "@/components/tools/MaterialGauge";
import type { useMaterialMeasure } from "@/hooks/useMaterialMeasure";
import type { useModules } from "@/hooks/useModules";

type Messung = ReturnType<typeof useMaterialMeasure>;
type Modules = ReturnType<typeof useModules>;

/** The prepared material of the demo: its workspace and files, shown but not changeable. */
export function DemoSources({ workspace, files }: { workspace: string; files: string[] }) {
  const tDemo = useTranslations("tools.pagesDemo");
  return (
    <div className="space-y-4">
      <Select id="pages-module" ariaLabel="Workspace" value="demo" onChange={() => {}} disabled
        options={[{ value: "demo", label: workspace }]} />
      <div>
        <ul className="space-y-2">
          {files.map((name) => (
            <li key={name}>
              <Checkbox checked disabled onChange={() => {}} label={name} className="min-w-0 max-w-full"
                labelClassName="text-sm text-foreground truncate min-w-0" />
            </li>
          ))}
        </ul>
        <p className="mt-2 text-xs text-muted">{tDemo("materialVorgegeben")}</p>
      </div>
    </div>
  );
}

interface FileProps {
  files: File[];
  extensions: string[];
  maxSources: number;
  sending: boolean;
  messung: Messung;
  onAdd: (files: File[]) => void;
  onRemove: (index: number) => void;
}

/** The drop zone for own files and the chosen files below it, each with its measure. */
export function FileSources({ files, extensions, maxSources, sending, messung, onAdd, onRemove }: FileProps) {
  const t = useTranslations("tools.pages");
  const tCommon = useTranslations("common");
  const [dragActive, setDragActive] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const full = files.length >= maxSources;
  return (
    <>
      <div
        role="button"
        tabIndex={0}
        aria-label={t("selectFileAria")}
        onClick={() => !sending && !full && inputRef.current?.click()}
        onKeyDown={(e) => {
          if ((e.key === "Enter" || e.key === " ") && !sending && !full) { e.preventDefault(); inputRef.current?.click(); }
        }}
        onDrop={(e) => { e.preventDefault(); setDragActive(false); if (!sending) onAdd(Array.from(e.dataTransfer.files)); }}
        onDragOver={(e) => { e.preventDefault(); if (!sending && !full) setDragActive(true); }}
        onDragLeave={() => setDragActive(false)}
        className={[
          "border-2 border-dashed rounded-lg p-8 text-center transition-colors bg-background",
          "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-kb",
          dragActive ? "border-kb bg-info-bg" : files.length ? "border-kb60" : "border-border hover:border-kb",
          sending || full ? "opacity-50 cursor-not-allowed" : "cursor-pointer",
        ].join(" ")}
      >
        <p className="text-sm font-medium text-muted">
          {tCommon("dropOrBrowse")} <span className="text-kb underline">{tCommon("browse")}</span>
        </p>
        <p className="text-xs text-muted-soft mt-1">{t("formats", { exts: extensions.join(", "), max: maxSources })}</p>
      </div>
      <input
        ref={inputRef}
        type="file"
        multiple
        accept={extensions.join(",")}
        onChange={(e) => { onAdd(Array.from(e.target.files ?? [])); if (inputRef.current) inputRef.current.value = ""; }}
        className="hidden"
        aria-hidden="true"
      />
      {files.length > 0 && (
        <div className="mt-4">
          <MaterialGauge bilanz={messung} max={messung.max} />
          <ul className="space-y-1">
            {files.map((f, i) => (
              <li key={`${f.name}-${f.size}`} className="text-sm text-foreground">
                <div className="flex items-center justify-between gap-3">
                  <span className="truncate">{f.name}</span>
                  <span className="flex items-center gap-3 shrink-0 whitespace-nowrap">
                    <MeasureNote messung={messung.forFile(f)} />
                    {!sending && (
                      <button type="button" onClick={() => onRemove(i)}
                        className="text-xs text-muted hover:text-foreground">
                        {t("removeFile")}
                      </button>
                    )}
                  </span>
                </div>
                <MeasureError messung={messung.forFile(f)} />
              </li>
            ))}
          </ul>
        </div>
      )}
    </>
  );
}

interface ModuleProps {
  modules: NonNullable<Modules["modules"]>;
  sources: Modules["sources"];
  moduleId: string;
  sourceIds: string[];
  maxSources: number;
  sending: boolean;
  messung: Messung;
  onModule: (uuid: string) => void;
  onToggle: (uuid: string) => void;
}

/** The choice of a workspace and of its sources, capped at the most a page takes. */
export function ModuleSources({ modules, sources, moduleId, sourceIds, maxSources, sending, messung, onModule, onToggle }: ModuleProps) {
  const t = useTranslations("tools.pages");
  const tCommon = useTranslations("common");
  const voll = sourceIds.length >= maxSources;
  return (
    <div className="space-y-4">
      <Select
        id="pages-module"
        ariaLabel="Workspace"
        value={moduleId}
        onChange={onModule}
        disabled={sending}
        placeholder={tCommon("pleaseSelect")}
        options={modules.map((m) => ({ value: m.uuid, label: m.title }))}
      />
      {moduleId && (sources === null ? (
        <Spinner className="justify-center py-6" />
      ) : sources.length === 0 ? (
        <EmptyState size="sm" text={t("noSources")} />
      ) : (
        <div>
          {sourceIds.length > 0 && <MaterialGauge bilanz={messung} max={messung.max} />}
          <ul className="space-y-2">
            {sources.map((q) => (
              <li key={q.uuid}>
                <div className="flex items-center justify-between gap-3">
                  {/* The card is narrow, a long name is cut so the count stays inside it. */}
                  <span className="min-w-0 flex-1" title={q.filename}>
                    <Checkbox
                      checked={sourceIds.includes(q.uuid)}
                      disabled={sending || (voll && !sourceIds.includes(q.uuid))}
                      onChange={() => onToggle(q.uuid)}
                      label={q.filename}
                      className="min-w-0 max-w-full"
                      labelClassName="text-sm text-foreground truncate min-w-0"
                    />
                  </span>
                  {sourceIds.includes(q.uuid) && (
                    <span className="shrink-0 whitespace-nowrap"><MeasureNote messung={messung.forSource(q.uuid)} /></span>
                  )}
                </div>
                {sourceIds.includes(q.uuid) && <MeasureError messung={messung.forSource(q.uuid)} />}
              </li>
            ))}
          </ul>
          <p className={`mt-2 text-xs ${voll ? "text-error font-medium" : "text-muted"}`}>{t("tooManySources", { max: maxSources })}</p>
        </div>
      ))}
    </div>
  );
}

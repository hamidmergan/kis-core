"use client";

import { useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { ArrowsClockwise, Cube, DotsThreeVertical, DownloadSimple, NotePencil, Plus, Trash, UploadSimple, Warning } from "@phosphor-icons/react";
import type { Provider } from "./_types";

const _PROBE_ERROR_CODES = new Set([
  "unreachable",
  "auth_rejected",
  "server_error",
  "endpoint_not_found",
]);

type Props = {
  providers: Provider[];
  onAdd: () => void;
  onEdit: (p: Provider) => void;
  onProbe: (p: Provider) => Promise<void> | void;
  onDelete: (p: Provider) => void;
  onExport: () => void | Promise<void>;
  onImport: (file: File) => void | Promise<void>;
  onClearAll: () => void;
};

export default function ProviderListCard({
  providers,
  onAdd,
  onEdit,
  onProbe,
  onDelete,
  onExport,
  onImport,
  onClearAll,
}: Props) {
  const t = useTranslations("admin.providers");
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <section className="border border-border-soft rounded-xl bg-background p-5">
      <div className="flex items-start justify-between gap-4 mb-1">
        <div>
          <div className="flex items-center gap-2 text-sm font-medium text-foreground">
            {t("list.title")}
            <span className="bg-surface-dim text-muted text-[11px] font-mono px-1.5 py-0.5 rounded-full">
              {providers.length}
            </span>
          </div>
          <p className="text-xs text-muted-soft mt-1 mb-4 max-w-2xl">{t("list.hint")}</p>
        </div>
        {providers.length > 0 && (
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={onExport}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-foreground border border-border-soft bg-background rounded-md hover:bg-surface transition-colors"
            >
              <DownloadSimple size={14} weight="bold" />
              {t("exportImport.exportButton")}
            </button>
            <input
              ref={fileInputRef}
              type="file"
              accept="application/json"
              className="hidden"
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) onImport(file);
                e.target.value = "";  // allow re-selecting the same file
              }}
            />
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-foreground border border-border-soft bg-background rounded-md hover:bg-surface transition-colors"
            >
              <UploadSimple size={14} weight="bold" />
              {t("exportImport.importButton")}
            </button>
            <button
              type="button"
              onClick={onAdd}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium bg-kb text-white rounded-md border-2 border-kb hover:bg-background hover:text-kb transition-colors"
            >
              <Plus size={14} weight="bold" />
              {t("list.add")}
            </button>
            <div className="relative">
              <button
                type="button"
                onClick={() => setMenuOpen((v) => !v)}
                aria-label="More actions"
                className="w-8 h-8 inline-flex items-center justify-center text-muted border border-border-soft rounded-md bg-background hover:bg-surface"
              >
                <DotsThreeVertical size={16} weight="bold" />
              </button>
              {menuOpen && (
                <>
                  <div
                    className="fixed inset-0 z-40"
                    onClick={() => setMenuOpen(false)}
                  />
                  <div className="absolute right-0 top-full mt-1 w-48 bg-background border border-border-soft rounded-md shadow-lg z-50 py-1">
                    <button
                      type="button"
                      onClick={() => {
                        setMenuOpen(false);
                        onClearAll();
                      }}
                      className="w-full text-left px-3 py-2 text-sm text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-950/30"
                    >
                      {t("clearAll.menuItem")}
                    </button>
                  </div>
                </>
              )}
            </div>
          </div>
        )}
      </div>

      {providers.length === 0 ? (
        <EmptyState onAdd={onAdd} onImport={onImport} />
      ) : (
        <div className="-my-3 divide-y divide-border-soft">
          {providers.map((p) => (
            <ProviderRow
              key={p.id}
              provider={p}
              onEdit={() => onEdit(p)}
              onProbe={() => onProbe(p)}
              onDelete={() => onDelete(p)}
            />
          ))}
        </div>
      )}
    </section>
  );
}

function EmptyState({ onAdd, onImport }: { onAdd: () => void; onImport: (file: File) => void | Promise<void> }) {
  const t = useTranslations("admin.providers");
  const fileInputRef = useRef<HTMLInputElement>(null);
  return (
    <div className="text-center py-10 px-6 border border-dashed border-border-soft rounded-lg">
      <Cube size={32} weight="bold" className="mx-auto text-muted mb-3" />
      <p className="text-sm font-medium text-foreground mb-1">{t("list.emptyTitle")}</p>
      <p className="text-xs text-muted-soft mb-4 max-w-md mx-auto">{t("list.emptyHint")}</p>
      <div className="flex items-center justify-center gap-2">
        <button
          type="button"
          onClick={onAdd}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium bg-kb text-white rounded-md border-2 border-kb hover:bg-background hover:text-kb transition-colors"
        >
          <Plus size={14} weight="bold" />
          {t("list.add")}
        </button>
        <input
          ref={fileInputRef}
          type="file"
          accept="application/json"
          className="hidden"
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) onImport(file);
            e.target.value = "";
          }}
        />
        <button
          type="button"
          onClick={() => fileInputRef.current?.click()}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-foreground border border-border-soft bg-background rounded-md hover:bg-surface transition-colors"
        >
          <UploadSimple size={14} weight="bold" />
          {t("exportImport.importButton")}
        </button>
      </div>
    </div>
  );
}

function providerNeedsKey(p: Provider): boolean {
  if (p.api_key_set) return false;
  if (p.protocol === "deepl") return true;
  if (p.protocol === "openai_compat") {
    const url = p.base_url.toLowerCase();
    if (url.includes("localhost") || url.includes("127.0.0.1") || url.includes("0.0.0.0")) {
      return false;
    }
    return true;
  }
  return false;
}

function ProviderRow({
  provider,
  onEdit,
  onProbe,
  onDelete,
}: {
  provider: Provider;
  onEdit: () => void;
  onProbe: () => Promise<void> | void;
  onDelete: () => void;
}) {
  const t = useTranslations("admin.providers");
  const [probing, setProbing] = useState(false);

  const handleProbe = async () => {
    setProbing(true);
    try {
      await onProbe();
    } finally {
      setProbing(false);
    }
  };

  return (
    <div className="grid grid-cols-[auto_1fr_auto] gap-4 items-center py-4">
      <div className="w-9 h-9 bg-surface border border-border-soft rounded-lg flex items-center justify-center text-kb">
        <Cube size={18} weight="bold" />
      </div>
      <div className="min-w-0">
        <div className="flex items-center gap-2 text-sm font-medium text-foreground mb-0.5">
          <span className="truncate">{provider.name}</span>
          <StatusPill provider={provider} probing={probing} />
          {providerNeedsKey(provider) && (
            <span
              title={t("row.missingKeyTooltip")}
              className="inline-flex items-center text-amber-500"
            >
              <Warning size={14} weight="fill" />
            </span>
          )}
        </div>
        <div className="text-[11.5px] font-mono text-muted truncate">
          {provider.base_url}
          {provider.api_key_set && provider.api_key_last_chars && (
            <span className="ml-2">{t("row.keySuffix", { chars: provider.api_key_last_chars })}</span>
          )}
        </div>
        {provider.probe_status === "error" && provider.probe_error && (
          <p className="mt-2 text-[11px] text-error">
            {_PROBE_ERROR_CODES.has(provider.probe_error)
              ? t(`probeErrors.${provider.probe_error}` as Parameters<typeof t>[0])
              : provider.probe_error}
          </p>
        )}
      </div>
      <div className="flex gap-1">
        <IconButton onClick={handleProbe} label={t("row.probe")} disabled={probing}>
          <ArrowsClockwise size={14} weight="bold" className={probing ? "animate-spin" : undefined} />
        </IconButton>
        <IconButton onClick={onEdit} label={t("row.edit")}>
          <NotePencil size={14} weight="bold" />
        </IconButton>
        <IconButton onClick={onDelete} label={t("row.delete")} danger>
          <Trash size={14} weight="bold" />
        </IconButton>
      </div>
    </div>
  );
}

function StatusPill({ provider, probing }: { provider: Provider; probing?: boolean }) {
  const t = useTranslations("admin.providers");
  if (probing) {
    return (
      <span className="inline-flex items-center gap-1 text-[11px] font-medium px-1.5 py-0.5 rounded-full bg-surface-dim text-muted">
        <span className="w-1.5 h-1.5 rounded-full bg-muted animate-pulse" />
        {t("row.statusChecking")}
      </span>
    );
  }
  if (provider.probe_status === "error") {
    return (
      <span className="inline-flex items-center gap-1 text-[11px] font-medium px-1.5 py-0.5 rounded-full bg-error-bg text-error-strong">
        <span className="w-1.5 h-1.5 rounded-full bg-error" />
        {t("row.statusError")}
      </span>
    );
  }
  if (!provider.probe_status) {
    return (
      <span className="inline-flex items-center gap-1 text-[11px] font-medium px-1.5 py-0.5 rounded-full bg-warn-bg text-warn-strong">
        <span className="w-1.5 h-1.5 rounded-full bg-warn" />
        {t("row.statusUnprobed")}
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 text-[11px] font-medium px-1.5 py-0.5 rounded-full bg-success-bg text-success-strong">
      <span className="w-1.5 h-1.5 rounded-full bg-success" />
      {t("row.statusActive")}
    </span>
  );
}

function IconButton({
  onClick,
  label,
  danger,
  disabled,
  children,
}: {
  onClick: () => void;
  label: string;
  danger?: boolean;
  disabled?: boolean;
  children: React.ReactNode;
}) {
  const stateClass = disabled
    ? "text-muted opacity-50 cursor-not-allowed"
    : danger
      ? "text-muted hover:text-error hover:border-transparent hover:outline hover:outline-2 hover:outline-error"
      : "text-muted hover:text-kb hover:border-transparent hover:outline hover:outline-2 hover:outline-kb";
  return (
    <button
      type="button"
      onClick={onClick}
      title={label}
      aria-label={label}
      disabled={disabled}
      className={`w-8 h-8 rounded-md border border-border-soft bg-background flex items-center justify-center transition-colors ${stateClass}`}
    >
      {children}
    </button>
  );
}

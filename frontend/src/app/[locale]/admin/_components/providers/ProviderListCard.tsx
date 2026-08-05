"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { ArrowsClockwise, Cube, NotePencil, Plus, Trash, UploadSimple } from "@phosphor-icons/react";
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
  onToggleEnabled: (p: Provider, enabled: boolean) => Promise<void> | void;
  onOpenExportImport: (initialTab: "export" | "import") => void;
};

export default function ProviderListCard({
  providers,
  onAdd,
  onEdit,
  onProbe,
  onDelete,
  onToggleEnabled,
  onOpenExportImport,
}: Props) {
  const t = useTranslations("admin.providers");

  return (
    <section className="border border-border-soft rounded-xl bg-background p-5">
      <div className="mb-1">
        <div className="flex items-center justify-between gap-4">
          <div className="flex items-center gap-2 text-sm font-medium text-foreground">
            {t("list.title")}
            <span className="bg-surface-dim text-muted text-2xs font-mono px-1.5 py-0.5 rounded-full">
              {providers.length}
            </span>
          </div>
          {providers.length > 0 && (
            <button
              type="button"
              onClick={onAdd}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium bg-kb text-white rounded-md border-2 border-kb hover:bg-background hover:text-kb transition-colors"
            >
              <Plus size={14} weight="bold" />
              {t("list.add")}
            </button>
          )}
        </div>
        <p className="text-xs text-muted-soft mt-1 mb-4">{t("list.hint")}</p>
      </div>

      {providers.length === 0 ? (
        <EmptyState onAdd={onAdd} onOpenExportImport={onOpenExportImport} />
      ) : (
        <div className="-my-3 divide-y divide-border-soft">
          {providers.map((p) => (
            <ProviderRow
              key={p.id}
              provider={p}
              onEdit={() => onEdit(p)}
              onProbe={() => onProbe(p)}
              onDelete={() => onDelete(p)}
              onToggleEnabled={(enabled) => onToggleEnabled(p, enabled)}
            />
          ))}
        </div>
      )}
    </section>
  );
}

function EmptyState({
  onAdd,
  onOpenExportImport,
}: {
  onAdd: () => void;
  onOpenExportImport: (initialTab: "export" | "import") => void;
}) {
  const t = useTranslations("admin.providers");
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
        <button
          type="button"
          onClick={() => onOpenExportImport("import")}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-foreground border border-border-soft bg-background rounded-md hover:bg-surface transition-colors"
        >
          <UploadSimple size={14} weight="bold" />
          {t("exportImport.importButton")}
        </button>
      </div>
    </div>
  );
}


function ProviderRow({
  provider,
  onEdit,
  onProbe,
  onDelete,
  onToggleEnabled,
}: {
  provider: Provider;
  onEdit: () => void;
  onProbe: () => Promise<void> | void;
  onDelete: () => void;
  onToggleEnabled: (enabled: boolean) => Promise<void> | void;
}) {
  const t = useTranslations("admin.providers");
  const [probing, setProbing] = useState(false);
  const [toggling, setToggling] = useState(false);

  const handleProbe = async () => {
    setProbing(true);
    try {
      await onProbe();
    } finally {
      setProbing(false);
    }
  };

  const handleToggle = async () => {
    setToggling(true);
    try {
      await onToggleEnabled(!provider.enabled);
    } finally {
      setToggling(false);
    }
  };

  const dimmed = provider.enabled ? "" : "opacity-50";

  return (
    <div className="grid grid-cols-[auto_1fr_auto] gap-4 items-center py-4">
      <div className={`w-9 h-9 bg-surface border border-border-soft rounded-lg flex items-center justify-center text-kb ${dimmed}`}>
        <Cube size={18} weight="bold" />
      </div>
      <div className={`min-w-0 ${dimmed}`}>
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-sm font-medium text-foreground mb-0.5">
          <span className="truncate">{provider.name}</span>
          {!provider.enabled && (
            <span className="inline-flex items-center text-2xs font-medium px-1.5 py-0.5 rounded-full bg-surface-dim text-muted">
              {t("row.disabledChip")}
            </span>
          )}
          <StatusPill provider={provider} probing={probing} />
          {!provider.api_key_set && (
            <span className="inline-flex items-center text-2xs font-medium px-1.5 py-0.5 rounded-full bg-surface-dim text-muted">
              {t("row.noApiKeyChip")}
            </span>
          )}
        </div>
        <div className="text-2xs font-mono text-muted truncate">
          {provider.base_url}
          {provider.api_key_set && provider.api_key_last_chars && (
            <span className="ml-2">{t("row.keySuffix", { chars: provider.api_key_last_chars })}</span>
          )}
        </div>
        {provider.probe_status === "error" && provider.probe_error && (
          <p className="mt-2 text-2xs text-error">
            {_PROBE_ERROR_CODES.has(provider.probe_error)
              ? t(`probeErrors.${provider.probe_error}` as Parameters<typeof t>[0])
              : provider.probe_error}
          </p>
        )}
      </div>
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={handleToggle}
          disabled={toggling}
          aria-label={provider.enabled ? t("row.disable") : t("row.enable")}
          title={provider.enabled ? t("row.disable") : t("row.enable")}
          className={`relative inline-flex shrink-0 w-11 h-6 rounded-full border-2 border-transparent transition-colors duration-200 focus:outline-none enabled:hover:border-kb disabled:opacity-50 ${
            provider.enabled ? "bg-kb" : "bg-border"
          }`}
        >
          <span
            className={`pointer-events-none inline-block w-5 h-5 bg-white rounded-full shadow transition-transform duration-200 ${
              provider.enabled ? "translate-x-5" : "translate-x-0"
            }`}
          />
        </button>
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
    </div>
  );
}

function StatusPill({ provider, probing }: { provider: Provider; probing?: boolean }) {
  const t = useTranslations("admin.providers");
  if (probing) {
    return (
      <span className="inline-flex items-center gap-1 text-2xs font-medium px-1.5 py-0.5 rounded-full bg-surface-dim text-muted">
        <span className="w-1.5 h-1.5 rounded-full bg-muted animate-pulse" />
        {t("row.statusChecking")}
      </span>
    );
  }
  if (provider.probe_status === "error") {
    return (
      <span className="inline-flex items-center gap-1 text-2xs font-medium px-1.5 py-0.5 rounded-full bg-error-bg text-error-strong">
        <span className="w-1.5 h-1.5 rounded-full bg-error" />
        {t("row.statusError")}
      </span>
    );
  }
  if (!provider.probe_status) {
    return (
      <span className="inline-flex items-center gap-1 text-2xs font-medium px-1.5 py-0.5 rounded-full bg-warn-bg text-warn-strong">
        <span className="w-1.5 h-1.5 rounded-full bg-warn" />
        {t("row.statusUnprobed")}
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 text-2xs font-medium px-1.5 py-0.5 rounded-full bg-success-bg text-success-strong">
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

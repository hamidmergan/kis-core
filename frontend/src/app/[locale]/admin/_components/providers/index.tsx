"use client";

import { useCallback, useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { DotsThreeVertical } from "@phosphor-icons/react";
import Spinner from "@/components/ui/Spinner";
import type { Feature, FeatureRoute, Provider, ProviderMeta } from "./_types";
import {
  clearAllProviders,
  createProvider,
  deleteProvider,
  fetchAffectedFeatures,
  fetchMeta,
  fetchProviders,
  fetchRoutes,
  importConfig,
  importPreview,
  probeProvider,
  setFeatureRoute,
  updateProvider,
} from "./_api";
import ProviderListCard from "./ProviderListCard";
import ProviderFormDialog from "./ProviderFormDialog";
import FeatureRoutingCard from "./FeatureRoutingCard";
import ExportImportDialog from "./ExportImportDialog";
import ClearAllConfirmDialog from "./ClearAllConfirmDialog";
import DeleteProviderConfirmDialog from "./DeleteProviderConfirmDialog";

type DialogState =
  | { open: false }
  | { open: true; mode: "create" }
  | { open: true; mode: "edit"; provider: Provider }
  | { open: true; mode: "export-import"; initialTab: "export" | "import" };

export default function ProvidersTab() {
  const t = useTranslations("admin.providers");
  const [meta, setMeta] = useState<ProviderMeta | null>(null);
  const [providers, setProviders] = useState<Provider[]>([]);
  const [routes, setRoutes] = useState<FeatureRoute[]>([]);
  const [loading, setLoading] = useState(true);
  const [dialog, setDialog] = useState<DialogState>({ open: false });
  const [clearAllOpen, setClearAllOpen] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<
    { provider: Provider; affectedFeatures: Feature[] } | null
  >(null);

  const refreshAll = useCallback(async () => {
    const [m, p, r] = await Promise.all([fetchMeta(), fetchProviders(), fetchRoutes()]);
    setMeta(m);
    setProviders(p);
    setRoutes(r);
  }, []);

  useEffect(() => {
    refreshAll().finally(() => setLoading(false));
  }, [refreshAll]);

  // ── provider mutations ──────────────────────────────────────────────────
  const handleSubmit = useCallback(
    async (data: {
      name: string;
      protocol: string;
      base_url: string;
      api_key: string | null;
      voices: import("./_types").Voice[];
      initial_capabilities?: string[];
      capabilities?: string[];
    }) => {
      if (dialog.open && dialog.mode === "edit") {
        // For edits, only patch fields the dialog actually changes. api_key
        // null means "leave existing key untouched"; empty string would clear.
        const patch: Record<string, unknown> = {
          name: data.name,
          base_url: data.base_url,
          voices: data.voices,
        };
        if (data.api_key !== null) {
          patch.api_key = data.api_key;
        }
        if (data.capabilities !== undefined) {
          patch.capabilities = data.capabilities;
        }
        await updateProvider(dialog.provider.id, patch);
      } else {
        await createProvider({
          name: data.name,
          protocol: data.protocol,
          base_url: data.base_url,
          api_key: data.api_key,
          voices: data.voices,
          initial_capabilities: data.initial_capabilities,
        });
      }
      await refreshAll();
    },
    [dialog, refreshAll],
  );

  const handleProbe = useCallback(
    async (p: Provider) => {
      await probeProvider(p.id);
      await refreshAll();
    },
    [refreshAll],
  );

  const handleDelete = useCallback(async (p: Provider) => {
    const affected = await fetchAffectedFeatures(p.id);
    setDeleteTarget({
      provider: p,
      affectedFeatures: affected.map((a) => a.feature),
    });
  }, []);

  const handleDeleteConfirm = useCallback(async () => {
    if (!deleteTarget) return;
    await deleteProvider(deleteTarget.provider.id);
    setDeleteTarget(null);
    await refreshAll();
  }, [deleteTarget, refreshAll]);

  // ── route mutations ─────────────────────────────────────────────────────
  const onChangeProvider = useCallback(
    async (feature: Feature, providerId: number | null) => {
      const existing = routes.find((r) => r.feature === feature);
      const carriedModel =
        providerId != null
          ? existing?.provider_models?.[String(providerId)] ?? null
          : null;
      await setFeatureRoute(feature, {
        provider_id: providerId,
        model_name: carriedModel,
        user_choices: existing?.user_choices ?? null,
        provider_models: existing?.provider_models,
      });
      await refreshAll();
    },
    [routes, refreshAll],
  );

  const onChangeModel = useCallback(
    async (feature: Feature, modelName: string | null) => {
      const existing = routes.find((r) => r.feature === feature);
      if (!existing?.provider_id) return;
      const nextProviderModels = { ...(existing.provider_models ?? {}) };
      const key = String(existing.provider_id);
      if (modelName) {
        nextProviderModels[key] = modelName;
      } else {
        delete nextProviderModels[key];
      }
      await setFeatureRoute(feature, {
        provider_id: existing.provider_id,
        model_name: modelName,
        user_choices: existing.user_choices ?? null,
        provider_models: nextProviderModels,
      });
      await refreshAll();
    },
    [routes, refreshAll],
  );

  const onChangeProviderModel = useCallback(
    async (feature: Feature, providerId: number, modelName: string | null) => {
      const existing = routes.find((r) => r.feature === feature);
      const next = { ...(existing?.provider_models ?? {}) };
      if (modelName) {
        next[String(providerId)] = modelName;
      } else {
        delete next[String(providerId)];
      }
      await setFeatureRoute(feature, {
        provider_id: existing?.provider_id ?? null,
        model_name: existing?.model_name ?? null,
        user_choices: existing?.user_choices ?? null,
        provider_models: next,
      });
      await refreshAll();
    },
    [routes, refreshAll],
  );

  const onToggleUserChoice = useCallback(
    async (feature: Feature, providerId: number, on: boolean) => {
      const existing = routes.find((r) => r.feature === feature);
      const current = existing?.user_choices ?? [];
      const nextChoices = on
        ? Array.from(new Set([...current, providerId]))
        : current.filter((id) => id !== providerId);
      // Default provider for the row: first choice (so resolve() has something
      // to return when no user runtime pick is supplied).
      const defaultProvider = nextChoices[0] ?? null;
      await setFeatureRoute(feature, {
        provider_id: defaultProvider,
        model_name: existing?.model_name ?? null,
        user_choices: nextChoices,
      });
      await refreshAll();
    },
    [routes, refreshAll],
  );

  const handleExportDownload = useCallback((config: unknown, filename: string) => {
    const blob = new Blob([JSON.stringify(config, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    setDialog({ open: false });
  }, []);

  const handleImportConfirm = useCallback(async (config: unknown) => {
    await importConfig(config);
    setDialog({ open: false });
    await refreshAll();
  }, [refreshAll]);

  const handleOpenExportImport = useCallback((initialTab: "export" | "import") => {
    setDialog({ open: true, mode: "export-import", initialTab });
  }, []);

  const handleClearAllRequest = useCallback(() => {
    setClearAllOpen(true);
  }, []);

  const handleClearAllConfirm = useCallback(async () => {
    try {
      await clearAllProviders();
      setClearAllOpen(false);
      await refreshAll();
      window.alert(t("clearAll.successToast"));
    } catch (err) {
      window.alert((err as Error).message);
    }
  }, [refreshAll, t]);

  if (loading || !meta) {
    return <Spinner className="flex justify-center py-12" />;
  }

  return (
    <div className="space-y-4">
      <header className="flex items-start justify-between gap-4">
        <p className="text-sm text-foreground-soft max-w-2xl">{t("intro")}</p>
        {providers.length > 0 && (
          <div className="relative shrink-0">
            <button
              type="button"
              onClick={() => setMenuOpen((v) => !v)}
              aria-label={t("list.moreActions")}
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
                <div className="absolute right-0 top-full mt-1 w-56 bg-background border border-border-soft rounded-md shadow-lg z-50 py-1">
                  <button
                    type="button"
                    onClick={() => {
                      setMenuOpen(false);
                      handleOpenExportImport("export");
                    }}
                    className="w-full text-left px-3 py-2 text-sm text-foreground hover:bg-surface"
                  >
                    {t("list.exportImportMenuItem")}
                  </button>
                  <div className="my-1 border-t border-border-soft" />
                  <button
                    type="button"
                    onClick={() => {
                      setMenuOpen(false);
                      handleClearAllRequest();
                    }}
                    className="w-full text-left px-3 py-2 text-sm text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-950/30"
                  >
                    {t("clearAll.menuItem")}
                  </button>
                </div>
              </>
            )}
          </div>
        )}
      </header>

      <ProviderListCard
        providers={providers}
        onAdd={() => setDialog({ open: true, mode: "create" })}
        onEdit={(p) => setDialog({ open: true, mode: "edit", provider: p })}
        onProbe={handleProbe}
        onDelete={handleDelete}
        onOpenExportImport={handleOpenExportImport}
      />

      {providers.length > 0 && (
        <FeatureRoutingCard
          meta={meta}
          providers={providers}
          routes={routes}
          onChangeProvider={onChangeProvider}
          onChangeModel={onChangeModel}
          onChangeProviderModel={onChangeProviderModel}
          onToggleUserChoice={onToggleUserChoice}
        />
      )}

      {dialog.open && (dialog.mode === "create" || dialog.mode === "edit") && (
        <ProviderFormDialog
          meta={meta}
          mode={dialog.mode}
          initial={dialog.mode === "edit" ? dialog.provider : undefined}
          onClose={() => setDialog({ open: false })}
          onSubmit={handleSubmit}
        />
      )}

      {dialog.open && dialog.mode === "export-import" && (
        <ExportImportDialog
          providers={providers}
          initialTab={dialog.initialTab}
          onClose={() => setDialog({ open: false })}
          onExportDownload={handleExportDownload}
          onImportPreview={importPreview}
          onImportConfirm={handleImportConfirm}
        />
      )}

      {clearAllOpen && (
        <ClearAllConfirmDialog
          providerCount={providers.length}
          routeCount={routes.length}
          onCancel={() => setClearAllOpen(false)}
          onConfirm={handleClearAllConfirm}
        />
      )}

      {deleteTarget && (
        <DeleteProviderConfirmDialog
          providerName={deleteTarget.provider.name}
          affectedFeatures={deleteTarget.affectedFeatures}
          onCancel={() => setDeleteTarget(null)}
          onConfirm={handleDeleteConfirm}
        />
      )}
    </div>
  );
}

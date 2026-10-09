"use client";

import { useCallback, useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { DotsThreeVertical } from "@phosphor-icons/react";
import Spinner from "@/components/ui/Spinner";
import type { Feature, FeatureRoute, ModelWindows, Provider, ProviderMeta, Sampling } from "./_types";
import { modelsOf, moved, orderedProviders } from "./_routeOptions";
import {
  clearAllProviders,
  createProvider,
  deleteProvider,
  fetchAffectedFeatures,
  fetchMeta,
  fetchModelWindows,
  fetchProviders,
  fetchRoutes,
  importConfig,
  importPreview,
  probeProvider,
  setFeatureRoute,
  updateProvider,
  type SetRouteInput,
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

/** Providers and features, 'only' picks which card is rendered. */
export default function ProvidersTab({ only }: { only?: "list" | "routes" } = {}) {
  const t = useTranslations("admin.providers");
  const [meta, setMeta] = useState<ProviderMeta | null>(null);
  const [providers, setProviders] = useState<Provider[]>([]);
  const [routes, setRoutes] = useState<FeatureRoute[]>([]);
  const [modelWindows, setModelWindows] = useState<ModelWindows | null>(null);
  const [loading, setLoading] = useState(true);
  const [dialog, setDialog] = useState<DialogState>({ open: false });
  const [clearAllOpen, setClearAllOpen] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<
    { provider: Provider; affectedFeatures: Feature[] } | null
  >(null);

  const refreshAll = useCallback(async () => {
    const [m, p, r, w] = await Promise.all([
      fetchMeta(), fetchProviders(), fetchRoutes(), fetchModelWindows(),
    ]);
    setMeta(m);
    setProviders(p);
    setRoutes(r);
    setModelWindows(w);
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
      concurrency?: Record<string, number>;
    }) => {
      if (dialog.open && dialog.mode === "edit") {
        // When editing, send only changed fields, null leaves the key in place.
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
        if (data.concurrency !== undefined) {
          patch.concurrency = data.concurrency;
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
          concurrency: data.concurrency,
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

  const handleToggleEnabled = useCallback(
    async (p: Provider, enabled: boolean) => {
      await updateProvider(p.id, { enabled });
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
  // Every save sends the whole order, the server takes first choice and fallback from it.
  const saveRoute = useCallback(
    async (feature: Feature, change: Partial<SetRouteInput>) => {
      const existing = routes.find((r) => r.feature === feature);
      await setFeatureRoute(feature, {
        user_choices: existing?.user_choices ?? null,
        provider_models: modelsOf(existing),
        provider_sampling: existing?.provider_sampling,
        provider_order: orderedProviders(feature, existing, providers).map((p) => p.id),
        ...change,
      });
      await refreshAll();
    },
    [routes, providers, refreshAll],
  );

  const onChangeProviderModel = useCallback(
    async (feature: Feature, providerId: number, modelName: string | null) => {
      const next = modelsOf(routes.find((r) => r.feature === feature));
      if (modelName) {
        next[String(providerId)] = modelName;
      } else {
        delete next[String(providerId)];
      }
      await saveRoute(feature, { provider_models: next });
    },
    [routes, saveRoute],
  );

  const onChangeSampling = useCallback(
    async (feature: Feature, providerId: number, werte: Sampling | null) => {
      const existing = routes.find((r) => r.feature === feature);
      const next = { ...(existing?.provider_sampling ?? {}) };
      if (werte) {
        next[String(providerId)] = werte;
      } else {
        delete next[String(providerId)];
      }
      await saveRoute(feature, { provider_sampling: next });
    },
    [routes, saveRoute],
  );

  const onToggleUserChoice = useCallback(
    async (feature: Feature, providerId: number, on: boolean) => {
      const existing = routes.find((r) => r.feature === feature);
      const current = existing?.user_choices ?? [];
      const nextChoices = on
        ? Array.from(new Set([...current, providerId]))
        : current.filter((id) => id !== providerId);
      // The first entry of the selection is the row's default provider.
      const rest = orderedProviders(feature, existing, providers).map((p) => p.id);
      await saveRoute(feature, {
        user_choices: nextChoices,
        provider_order: [...nextChoices, ...rest.filter((id) => !nextChoices.includes(id))],
      });
    },
    [routes, providers, saveRoute],
  );

  const onMove = useCallback(
    async (feature: Feature, providerId: number, step: -1 | 1) => {
      const order = orderedProviders(feature, routes.find((r) => r.feature === feature), providers).map((p) => p.id);
      await saveRoute(feature, { provider_order: moved(order, providerId, step) });
    },
    [routes, providers, saveRoute],
  );

  const handleExportDownload = useCallback((config: unknown, filename: string) => {
    const now = new Date();
    const time = [now.getHours(), now.getMinutes(), now.getSeconds()]
      .map((n) => String(n).padStart(2, "0"))
      .join("");
    const dot = filename.lastIndexOf(".");
    const stamped = dot >= 0
      ? `${filename.slice(0, dot)}-${time}${filename.slice(dot)}`
      : `${filename}-${time}`;
    const blob = new Blob([JSON.stringify(config, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = stamped;
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
      {only !== "routes" && <header className="flex items-start justify-between gap-4">
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
      </header>}

      {only !== "routes" && <ProviderListCard
        providers={providers}
        onAdd={() => setDialog({ open: true, mode: "create" })}
        onEdit={(p) => setDialog({ open: true, mode: "edit", provider: p })}
        onProbe={handleProbe}
        onDelete={handleDelete}
        onToggleEnabled={handleToggleEnabled}
        onOpenExportImport={handleOpenExportImport}
        modelWindows={modelWindows}
        onWindowSaved={refreshAll}
      />}

      {only !== "list" && providers.length > 0 && (
        <FeatureRoutingCard
          meta={meta}
          providers={providers}
          routes={routes}
          onChangeProviderModel={onChangeProviderModel}
          onChangeSampling={onChangeSampling}
          onToggleUserChoice={onToggleUserChoice}
          onMove={onMove}
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
          apiKeyEncryptionEnabled={meta.api_key_encryption_enabled}
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

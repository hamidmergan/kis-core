"use client";

import { useCallback, useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import Spinner from "@/components/ui/Spinner";
import type { Feature, FeatureRoute, ImportPreviewResult, Provider, ProviderMeta } from "./_types";
import {
  createProvider,
  deleteProvider,
  exportConfig,
  fetchAffectedFeatures,
  fetchMeta,
  fetchProviders,
  fetchRoutes,
  importPreview,
  probeProvider,
  setFeatureRoute,
  updateProvider,
} from "./_api";
import ProviderListCard from "./ProviderListCard";
import ProviderFormDialog from "./ProviderFormDialog";
import FeatureRoutingCard from "./FeatureRoutingCard";

type DialogState =
  | { open: false }
  | { open: true; mode: "create" }
  | { open: true; mode: "edit"; provider: Provider }
  | {
      open: true;
      mode: "import-preview";
      filename: string;
      config: unknown;
      preview: ImportPreviewResult;
    };

export default function ProvidersTab() {
  const t = useTranslations("admin.providers");
  const [meta, setMeta] = useState<ProviderMeta | null>(null);
  const [providers, setProviders] = useState<Provider[]>([]);
  const [routes, setRoutes] = useState<FeatureRoute[]>([]);
  const [loading, setLoading] = useState(true);
  const [dialog, setDialog] = useState<DialogState>({ open: false });

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

  const handleDelete = useCallback(
    async (p: Provider) => {
      const affected = await fetchAffectedFeatures(p.id);
      const confirmMsg =
        affected.length === 0
          ? t("delete.confirmEmpty", { name: p.name })
          : t("delete.confirmWithRoutes", {
              name: p.name,
              features: affected.map((a) => t(`featureName.${a.feature}`)).join(", "),
            });
      if (!window.confirm(confirmMsg)) return;
      await deleteProvider(p.id);
      await refreshAll();
    },
    [refreshAll, t],
  );

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

  const handleExport = useCallback(async () => {
    try {
      const { blob, filename } = await exportConfig();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      window.alert(t("exportImport.exportToast"));
    } catch (err) {
      window.alert((err as Error).message);
    }
  }, [t]);

  const handleImportFile = useCallback(async (file: File) => {
    try {
      const text = await file.text();
      let config: unknown;
      try {
        config = JSON.parse(text);
      } catch {
        window.alert(t("exportImport.errors.invalidJson"));
        return;
      }
      const preview = await importPreview(config);
      setDialog({
        open: true,
        mode: "import-preview",
        filename: file.name,
        config,
        preview,
      });
    } catch (err) {
      window.alert(t("exportImport.errors.importFailed", { message: (err as Error).message }));
    }
  }, [t]);

  if (loading || !meta) {
    return <Spinner className="flex justify-center py-12" />;
  }

  return (
    <div className="space-y-4">
      <p className="text-sm text-foreground-soft max-w-2xl">{t("intro")}</p>

      <ProviderListCard
        providers={providers}
        onAdd={() => setDialog({ open: true, mode: "create" })}
        onEdit={(p) => setDialog({ open: true, mode: "edit", provider: p })}
        onProbe={handleProbe}
        onDelete={handleDelete}
        onExport={handleExport}
        onImport={handleImportFile}
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
    </div>
  );
}

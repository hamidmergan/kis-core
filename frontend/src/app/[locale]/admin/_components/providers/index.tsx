"use client";

import { useCallback, useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import Spinner from "@/components/ui/Spinner";
import type { Feature, FeatureRoute, Provider, ProviderMeta } from "./_types";
import {
  createProvider,
  deleteProvider,
  fetchAffectedFeatures,
  fetchMeta,
  fetchProviders,
  fetchRoutes,
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
  | { open: true; mode: "edit"; provider: Provider };

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
    }) => {
      if (dialog.open && dialog.mode === "edit") {
        // For edits, only patch fields the dialog actually changes. api_key
        // null means "leave existing key untouched"; empty string would clear.
        const patch: Record<string, unknown> = {
          name: data.name,
          base_url: data.base_url,
        };
        if (data.api_key !== null) {
          patch.api_key = data.api_key;
        }
        await updateProvider(dialog.provider.id, patch);
      } else {
        await createProvider(data);
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
      await setFeatureRoute(feature, {
        provider_id: providerId,
        model_name: providerId ? existing?.model_name ?? null : null,
        user_choices: existing?.user_choices ?? null,
      });
      await refreshAll();
    },
    [routes, refreshAll],
  );

  const onChangeModel = useCallback(
    async (feature: Feature, modelName: string | null) => {
      const existing = routes.find((r) => r.feature === feature);
      if (!existing?.provider_id) return;
      await setFeatureRoute(feature, {
        provider_id: existing.provider_id,
        model_name: modelName,
        user_choices: existing.user_choices ?? null,
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
      />

      {providers.length > 0 && (
        <FeatureRoutingCard
          meta={meta}
          providers={providers}
          routes={routes}
          onChangeProvider={onChangeProvider}
          onChangeModel={onChangeModel}
          onToggleUserChoice={onToggleUserChoice}
        />
      )}

      {dialog.open && (
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

// The export references by name, so the filter works with names too.
type ExportedProvider = { name: string; [key: string]: unknown };
type ExportedRoute = {
  feature: string;
  provider_name: string | null;
  model_name: string | null;
  user_choices: string[];
  provider_models: Record<string, string>;
  [key: string]: unknown;
};
type ExportedConfig = {
  providers: ExportedProvider[];
  feature_routes: ExportedRoute[];
  [key: string]: unknown;
};

function isExportedConfig(value: unknown): value is ExportedConfig {
  if (typeof value !== "object" || value === null) return false;
  const v = value as Record<string, unknown>;
  return Array.isArray(v.providers) && Array.isArray(v.feature_routes);
}

/** Keeps only the chosen providers and tidies the routes accordingly. */
export function filterExportConfig(
  config: unknown,
  selectedNames: Set<string>,
): unknown {
  if (!isExportedConfig(config)) return config;
  const providers = config.providers.filter((p) => selectedNames.has(p.name));
  const feature_routes = config.feature_routes
    .filter((r) =>
      r.provider_name !== null
        ? selectedNames.has(r.provider_name)
        : // A voice route may stand on its fallback alone, so it travels with that fallback.
          r.feature === "tts" &&
          typeof r.fallback_provider_name === "string" &&
          selectedNames.has(r.fallback_provider_name),
    )
    .map((r) => ({
      ...r,
      user_choices: (r.user_choices ?? []).filter((n) => selectedNames.has(n)),
      provider_models: Object.fromEntries(
        Object.entries(r.provider_models ?? {}).filter(([name]) =>
          selectedNames.has(name),
        ),
      ),
      // A fallback whose provider stays behind is dropped, a missing field stays missing.
      ...(typeof r.fallback_provider_name === "string" &&
      !selectedNames.has(r.fallback_provider_name)
        ? { fallback_provider_name: null }
        : {}),
    }));
  return { ...config, providers, feature_routes };
}

// Shape of an exported JSON (subset we touch). Backend keys cross-refs by
// provider name, so the filter operates on names too.
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

/**
 * Keep only providers whose `name` is in `selectedNames`. For each route:
 * - drop the route if its `provider_name` is not selected;
 * - otherwise filter `user_choices` and `provider_models` keys to selected names.
 * Top-level fields (schema_version, exported_at, exported_from) pass through.
 */
export function filterExportConfig(
  config: unknown,
  selectedNames: Set<string>,
): unknown {
  if (!isExportedConfig(config)) return config;
  const providers = config.providers.filter((p) => selectedNames.has(p.name));
  const feature_routes = config.feature_routes
    .filter((r) => r.provider_name !== null && selectedNames.has(r.provider_name))
    .map((r) => ({
      ...r,
      user_choices: (r.user_choices ?? []).filter((n) => selectedNames.has(n)),
      provider_models: Object.fromEntries(
        Object.entries(r.provider_models ?? {}).filter(([name]) =>
          selectedNames.has(name),
        ),
      ),
    }));
  return { ...config, providers, feature_routes };
}

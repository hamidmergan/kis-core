import type { Capability, Feature, FeatureRoute, Provider } from "./_types";

/** The capability a fallback needs per feature, mirrors the backend rules. */
const FALLBACK_CAPABILITY: Record<Exclude<Feature, "tts">, Capability> = {
  chat: "chat",
  embedding: "embedding",
  vision: "vision",
  ocr: "ocr",
  stt: "stt",
  image_gen: "image_gen",
  image_edit: "image_edit",
  doc_translate: "chat",
  screencast_translate: "chat",
  transcript_translate: "chat",
};

type RouteModels = Pick<FeatureRoute, "provider_id" | "model_name" | "provider_models"> & {
  fallback_provider_id?: number | null;
};

export type FallbackOption = { id: number; name: string; model: string; usable: boolean };

function modelOf(route: RouteModels | undefined, providerId: number): string {
  return (route?.provider_models?.[String(providerId)] ?? "").trim();
}

/** The model the first choice runs with. */
function primaryModel(route: RouteModels): string {
  const id = route.provider_id;
  return ((id != null ? route.provider_models?.[String(id)] : "") || route.model_name || "").trim();
}

function candidates(feature: Feature, route: RouteModels | undefined, providers: Provider[]): Provider[] {
  if (feature === "tts" || !route) return [];
  const capability = FALLBACK_CAPABILITY[feature];
  const primary = primaryModel(route);
  return providers.filter((p) => {
    if (p.id === route.provider_id || !p.enabled || p.protocol !== "openai_compat") return false;
    if (!p.capabilities.includes(capability)) return false;
    const model = modelOf(route, p.id);
    if (!model) return false;
    return feature !== "embedding" || model === primary;
  });
}

/** Fallback choices of a feature, a stored fallback that broke stays listed as unusable. */
export function fallbackOptions(
  feature: Feature,
  route: RouteModels | undefined,
  providers: Provider[],
): FallbackOption[] {
  const options: FallbackOption[] = candidates(feature, route, providers).map((p) => ({
    id: p.id,
    name: p.name,
    model: modelOf(route, p.id),
    usable: true,
  }));
  const stored = route?.fallback_provider_id ?? null;
  const storedProvider = providers.find((p) => p.id === stored);
  if (storedProvider && !options.some((o) => o.id === stored)) {
    options.push({ id: storedProvider.id, name: storedProvider.name, model: modelOf(route, storedProvider.id), usable: false });
  }
  return options;
}

/** The stored fallback while it still satisfies the rules for this route, otherwise null. */
export function keptFallback(feature: Feature, route: RouteModels, providers: Provider[]): number | null {
  const stored = route.fallback_provider_id ?? null;
  if (stored == null) return null;
  return candidates(feature, route, providers).some((p) => p.id === stored) ? stored : null;
}

/** Providers of a row that can be the first choice, the current one always stays listed. */
export function firstChoiceOptions(route: RouteModels | undefined, listed: Provider[]): Provider[] {
  return listed.filter(
    (p) => p.id === route?.provider_id || p.protocol !== "openai_compat" || modelOf(route, p.id) !== "",
  );
}

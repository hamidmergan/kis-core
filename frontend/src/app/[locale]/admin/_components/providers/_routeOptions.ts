import type { Capability, Feature, FeatureRoute, Provider } from "./_types";

// One capability per feature, the provider list filters by it.
const FEATURE_CAPABILITY: Record<Feature, Capability> = {
  chat: "chat",
  embedding: "embedding",
  vision: "vision",
  ocr: "ocr",
  stt: "stt",
  tts: "tts",
  image_gen: "image_gen",
  image_edit: "image_edit",
  doc_translate: "translation",
  screencast_translate: "translation",
  transcript_translate: "translation",
};

// For translating a chat capable provider counts too.
const FEATURE_EXTRA_CAPABILITIES: Partial<Record<Feature, Capability[]>> = {
  doc_translate: ["chat"],
  screencast_translate: ["chat"],
  transcript_translate: ["chat"],
};

type RouteOrder = Pick<FeatureRoute, "provider_id" | "provider_models"> &
  Partial<Pick<FeatureRoute, "fallback_provider_id" | "provider_order" | "model_name">>;

/** The enabled providers that can serve a feature, in the order they were added. */
export function eligibleProviders(feature: Feature, providers: Provider[]): Provider[] {
  return providers.filter((p) => {
    if (!p.enabled) return false;
    const caps = new Set(p.capabilities);
    if (caps.has(FEATURE_CAPABILITY[feature])) return true;
    return (FEATURE_EXTRA_CAPABILITIES[feature] ?? []).some((c) => caps.has(c));
  });
}

/** The providers of a feature in the admin's order, a route without one puts first choice and fallback in front. */
export function orderedProviders(feature: Feature, route: RouteOrder | undefined, providers: Provider[]): Provider[] {
  const listed = eligibleProviders(feature, providers);
  const stored = route?.provider_order?.length
    ? route.provider_order
    : [route?.provider_id, route?.fallback_provider_id];
  const front = [...new Set(stored)]
    .map((id) => listed.find((p) => p.id === id))
    .filter((p): p is Provider => p !== undefined);
  return [...front, ...listed.filter((p) => !front.includes(p))];
}

/** The order after moving one provider a step up (-1) or down (+1). */
export function moved(order: number[], providerId: number, step: -1 | 1): number[] {
  const from = order.indexOf(providerId);
  const to = from + step;
  if (from < 0 || to < 0 || to >= order.length) return order;
  const next = [...order];
  [next[from], next[to]] = [next[to], next[from]];
  return next;
}

/** The models per provider, a route from before the per provider models keeps its first choice's model. */
export function modelsOf(route: RouteOrder | undefined): Record<string, string> {
  const models = { ...(route?.provider_models ?? {}) };
  const first = route?.provider_id;
  if (first != null && !models[String(first)] && route?.model_name) models[String(first)] = route.model_name;
  return models;
}

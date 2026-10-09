/** The order of the providers per feature, the first usable one is the standard. */
import { describe, expect, it } from "vitest";

import { eligibleProviders, modelsOf, moved, orderedProviders } from "./_routeOptions";
import type { FeatureRoute, Provider } from "./_types";

function anbieter(id: number, extra: Partial<Provider> = {}): Provider {
  return {
    id,
    name: `P${id}`,
    protocol: "openai_compat",
    base_url: "https://example.org",
    capabilities: ["chat", "vision", "embedding"],
    voices: [],
    enabled: true,
    last_probed_at: null,
    probe_status: null,
    probe_error: null,
    api_key_set: false,
    api_key_last_chars: null,
    created_at: "",
    updated_at: "",
    concurrency: {},
    ...extra,
  };
}

function route(extra: Partial<FeatureRoute> = {}): FeatureRoute {
  return {
    id: 1,
    feature: "chat",
    provider_id: 1,
    model_name: "m1",
    user_choices: [],
    provider_models: { "1": "m1", "2": "m2" },
    provider_sampling: {},
    updated_at: "",
    fallback_provider_id: null,
    provider_order: [],
    ...extra,
  };
}

const ids = (liste: Array<{ id: number }>) => liste.map((o) => o.id);

describe("eligibleProviders", () => {
  it("laesst abgeschaltete Anbieter und fremde Faehigkeiten weg", () => {
    const liste = [anbieter(1), anbieter(2, { enabled: false }), anbieter(3, { capabilities: ["tts"] })];
    expect(ids(eligibleProviders("chat", liste))).toEqual([1]);
  });

  it("nimmt beim Uebersetzen DeepL und LLM", () => {
    const liste = [anbieter(1), anbieter(4, { protocol: "deepl", capabilities: ["translation"] })];
    expect(ids(eligibleProviders("doc_translate", liste))).toEqual([1, 4]);
  });
});

describe("orderedProviders", () => {
  const liste = [anbieter(1), anbieter(2), anbieter(3)];

  it("folgt der gespeicherten Reihenfolge, der Rest haengt hinten an", () => {
    expect(ids(orderedProviders("chat", route({ provider_order: [3, 1] }), liste))).toEqual([3, 1, 2]);
  });

  it("stellt bei einer alten Route erste Wahl und Rueckfall nach vorn", () => {
    expect(ids(orderedProviders("chat", route({ provider_id: 3, fallback_provider_id: 2 }), liste))).toEqual([3, 2, 1]);
  });

  it("laesst geloeschte Anbieter aus der Reihenfolge fallen", () => {
    expect(ids(orderedProviders("chat", route({ provider_order: [9, 2] }), liste))).toEqual([2, 1, 3]);
  });

  it("vertraegt eine fehlende Route", () => {
    expect(ids(orderedProviders("chat", undefined, liste))).toEqual([1, 2, 3]);
  });
});

describe("moved", () => {
  it("tauscht mit dem Nachbarn", () => {
    expect(moved([1, 2, 3], 2, -1)).toEqual([2, 1, 3]);
    expect(moved([1, 2, 3], 2, 1)).toEqual([1, 3, 2]);
  });

  it("bleibt am Rand stehen", () => {
    expect(moved([1, 2, 3], 1, -1)).toEqual([1, 2, 3]);
    expect(moved([1, 2, 3], 3, 1)).toEqual([1, 2, 3]);
  });
});

describe("modelsOf", () => {
  it("holt das Modell einer alten ersten Wahl aus model_name", () => {
    expect(modelsOf(route({ provider_id: 3, model_name: "m3", provider_models: { "1": "m1" } }))).toEqual({ "1": "m1", "3": "m3" });
  });

  it("laesst ein eingetragenes Modell stehen", () => {
    expect(modelsOf(route({ model_name: "alt" }))).toEqual({ "1": "m1", "2": "m2" });
  });
});

/** Which providers the first choice and fallback dropdowns of a feature row offer. */
import { describe, expect, it } from "vitest";

import { fallbackOptions, firstChoiceMark, firstChoiceOptions, keptFallback } from "./_routeOptions";
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
    ...extra,
  };
}

const ids = (liste: Array<{ id: number }>) => liste.map((o) => o.id);

const stimme = { voice_id: "nova", name: "Nova", language: "de" };

describe("fallbackOptions", () => {
  it("bietet einen passenden Anbieter mit Modell an", () => {
    expect(fallbackOptions("chat", route(), [anbieter(1), anbieter(2)])).toEqual([
      { id: 2, name: "P2", model: "m2", usable: true },
    ]);
  });

  it("bietet nie die erste Wahl selbst an", () => {
    expect(ids(fallbackOptions("chat", route(), [anbieter(1)]))).toEqual([]);
  });

  it("laesst abgeschaltete Anbieter weg", () => {
    expect(ids(fallbackOptions("chat", route(), [anbieter(2, { enabled: false })]))).toEqual([]);
  });

  it("laesst Anbieter ohne OpenAI-kompatible Schnittstelle weg", () => {
    expect(ids(fallbackOptions("chat", route(), [anbieter(2, { protocol: "deepl" })]))).toEqual([]);
  });

  it("laesst Anbieter ohne die Faehigkeit der Funktion weg", () => {
    const p = anbieter(2, { capabilities: ["embedding"] });
    expect(ids(fallbackOptions("chat", route(), [p]))).toEqual([]);
  });

  it("laesst Anbieter ohne eingetragenes Modell weg", () => {
    const r = route({ provider_models: { "1": "m1", "2": "  " } });
    expect(ids(fallbackOptions("chat", r, [anbieter(2), anbieter(3)]))).toEqual([]);
  });

  it("bietet fuer Stimmen einen Anbieter mit Sprachausgabe und Stimmen an", () => {
    const p = anbieter(2, { capabilities: ["tts"], voices: [stimme] });
    expect(fallbackOptions("tts", route({ feature: "tts" }), [p])).toEqual([
      { id: 2, name: "P2", model: "m2", usable: true },
    ]);
  });

  it("laesst fuer Stimmen Anbieter ohne Stimmen weg", () => {
    const p = anbieter(2, { capabilities: ["tts"] });
    expect(ids(fallbackOptions("tts", route({ feature: "tts" }), [p]))).toEqual([]);
  });

  it("laesst fuer Stimmen Anbieter ohne Sprachausgabe weg", () => {
    const p = anbieter(2, { voices: [stimme] });
    expect(ids(fallbackOptions("tts", route({ feature: "tts" }), [p]))).toEqual([]);
  });

  it("verlangt bei Uebersetzungen die Chat-Faehigkeit", () => {
    const r = route({ feature: "doc_translate" });
    const nurUebersetzung = anbieter(2, { capabilities: ["translation"] });
    expect(ids(fallbackOptions("doc_translate", r, [nurUebersetzung]))).toEqual([]);
    expect(ids(fallbackOptions("doc_translate", r, [anbieter(2)]))).toEqual([2]);
  });

  it("nimmt bei Embeddings nur dasselbe Modell wie die erste Wahl", () => {
    const r = route({ feature: "embedding", provider_models: { "1": "e5", "2": "e5", "3": "bge" } });
    expect(ids(fallbackOptions("embedding", r, [anbieter(2), anbieter(3)]))).toEqual([2]);
  });

  it("liest das Modell der ersten Wahl bei Embeddings notfalls aus model_name", () => {
    const r = route({ feature: "embedding", model_name: "e5", provider_models: { "2": "e5" } });
    expect(ids(fallbackOptions("embedding", r, [anbieter(2)]))).toEqual([2]);
  });

  it("bietet bei Embeddings ohne Modell der ersten Wahl nichts an", () => {
    const r = route({ feature: "embedding", model_name: null, provider_models: { "2": "e5" } });
    expect(ids(fallbackOptions("embedding", r, [anbieter(2)]))).toEqual([]);
  });

  it("zeigt einen gespeicherten, nicht mehr nutzbaren Rueckfall als solchen", () => {
    const r = route({ fallback_provider_id: 2 });
    expect(fallbackOptions("chat", r, [anbieter(2, { enabled: false })])).toEqual([
      { id: 2, name: "P2", model: "m2", usable: false },
    ]);
  });

  it("bietet ohne Route nichts an", () => {
    expect(fallbackOptions("chat", undefined, [anbieter(2)])).toEqual([]);
  });
});

describe("keptFallback", () => {
  it("behaelt einen gueltigen Rueckfall", () => {
    expect(keptFallback("chat", route({ fallback_provider_id: 2 }), [anbieter(1), anbieter(2)])).toBe(2);
  });

  it("gibt null ohne gespeicherten Rueckfall", () => {
    expect(keptFallback("chat", route(), [anbieter(2)])).toBeNull();
  });

  it("verwirft den Rueckfall, sobald er zur ersten Wahl wird", () => {
    const r = route({ provider_id: 2, fallback_provider_id: 2 });
    expect(keptFallback("chat", r, [anbieter(1), anbieter(2)])).toBeNull();
  });

  it("verwirft den Rueckfall, wenn sein Modell geloescht wird", () => {
    const r = route({ provider_models: { "1": "m1" }, fallback_provider_id: 2 });
    expect(keptFallback("chat", r, [anbieter(2)])).toBeNull();
  });

  it("verwirft den Embedding-Rueckfall, wenn die erste Wahl das Modell wechselt", () => {
    const r = route({
      feature: "embedding",
      provider_models: { "1": "bge", "2": "e5" },
      fallback_provider_id: 2,
    });
    expect(keptFallback("embedding", r, [anbieter(2)])).toBeNull();
  });

  it("behaelt den Stimmen-Rueckfall beim Speichern", () => {
    const r = route({ feature: "tts", fallback_provider_id: 2 });
    const p = anbieter(2, { capabilities: ["tts"], voices: [stimme] });
    expect(keptFallback("tts", r, [anbieter(1), p])).toBe(2);
  });

  it("bietet bei Stimmen auch den Anbieter der Route als Rueckfall an", () => {
    // Die Person waehlt ihre Stimme selbst, der Anbieter der Route taugt als Rueckfall fuer Auftraege bei anderen.
    const r = route({ feature: "tts", provider_id: 2, fallback_provider_id: 2 });
    const p = anbieter(2, { capabilities: ["tts"], voices: [stimme] });
    expect(ids(fallbackOptions("tts", r, [p]))).toEqual([2]);
    expect(keptFallback("tts", r, [p])).toBe(2);
  });

  it("verwirft den Stimmen-Rueckfall, wenn er keine Stimmen mehr hat", () => {
    const r = route({ feature: "tts", fallback_provider_id: 2 });
    expect(keptFallback("tts", r, [anbieter(2, { capabilities: ["tts"] })])).toBeNull();
  });

  it("vertraegt eine Route ohne das Feld", () => {
    const r: Omit<FeatureRoute, "fallback_provider_id"> = route();
    expect(keptFallback("chat", r, [anbieter(2)])).toBeNull();
  });
});

describe("firstChoiceOptions", () => {
  it("listet Anbieter mit eingetragenem Modell", () => {
    const r = route({ provider_id: null, provider_models: { "2": "m2" } });
    expect(ids(firstChoiceOptions(r, [anbieter(2), anbieter(3)]))).toEqual([2]);
  });

  it("laesst Anbieter ohne Modellpflicht auch ohne Modell zu", () => {
    const r = route({ provider_id: null, provider_models: {} });
    expect(ids(firstChoiceOptions(r, [anbieter(2, { protocol: "deepl" }), anbieter(3)]))).toEqual([2]);
  });

  it("behaelt die aktuelle erste Wahl auch ohne Modell", () => {
    const r = route({ provider_id: 3, provider_models: {} });
    expect(ids(firstChoiceOptions(r, [anbieter(2), anbieter(3)]))).toEqual([3]);
  });

  it("listet ohne Route nur Anbieter ohne Modellpflicht", () => {
    expect(ids(firstChoiceOptions(undefined, [anbieter(2), anbieter(4, { protocol: "deepl" })]))).toEqual([4]);
  });
});

describe("firstChoiceMark", () => {
  it("zeigt die aktuelle erste Wahl als gesetzt, auch ohne Modell", () => {
    expect(firstChoiceMark(route({ provider_id: 3, provider_models: {} }), anbieter(3))).toBe("on");
  });

  it("gibt einen Anbieter mit Modell frei", () => {
    expect(firstChoiceMark(route(), anbieter(2))).toBe("free");
  });

  it("gibt einen Anbieter ohne Modellpflicht auch ohne Modell frei", () => {
    expect(firstChoiceMark(route({ provider_models: {} }), anbieter(4, { protocol: "deepl" }))).toBe("free");
  });

  it("sperrt einen Anbieter mit Modellpflicht ohne Modell", () => {
    expect(firstChoiceMark(route({ provider_models: { "1": "m1", "2": "  " } }), anbieter(2))).toBe("needsModel");
  });

  it("sperrt ohne Route jeden Anbieter mit Modellpflicht", () => {
    expect(firstChoiceMark(undefined, anbieter(2))).toBe("needsModel");
  });
});

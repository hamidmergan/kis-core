/** The export keeps only the chosen providers and tidies the routes to match. */
import { describe, expect, it } from "vitest";

import { filterExportConfig } from "./_exportFilter";

function exportMit(route: Record<string, unknown>) {
  return {
    schema_version: 1,
    providers: [{ name: "HPC" }, { name: "myLab" }],
    feature_routes: [
      {
        feature: "chat",
        provider_name: "HPC",
        model_name: "gemma",
        user_choices: [],
        provider_models: { HPC: "gemma", myLab: "qwen" },
        ...route,
      },
    ],
  };
}

type Gefiltert = { feature_routes: Array<Record<string, unknown>> };

describe("filterExportConfig", () => {
  it("behaelt den Rueckfall, wenn sein Anbieter mitkommt", () => {
    const out = filterExportConfig(exportMit({ fallback_provider_name: "myLab" }), new Set(["HPC", "myLab"]));
    expect((out as Gefiltert).feature_routes[0].fallback_provider_name).toBe("myLab");
  });

  it("leert den Rueckfall, wenn sein Anbieter nicht mitkommt", () => {
    const out = filterExportConfig(exportMit({ fallback_provider_name: "myLab" }), new Set(["HPC"]));
    const r = (out as Gefiltert).feature_routes[0];
    expect(r.fallback_provider_name).toBeNull();
    expect(r.provider_models).toEqual({ HPC: "gemma" });
  });

  it("fuegt kein Feld hinzu, das der Export nicht hatte", () => {
    const out = filterExportConfig(exportMit({}), new Set(["HPC"]));
    expect("fallback_provider_name" in (out as Gefiltert).feature_routes[0]).toBe(false);
  });
});

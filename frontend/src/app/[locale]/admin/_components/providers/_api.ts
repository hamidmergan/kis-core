import type {
  ClearAllResult,
  Feature,
  FeatureRoute,
  ImportPreviewResult,
  ImportResult,
  Provider,
  ProviderMeta,
  Voice,
} from "./_types";

const BASE = "/api/admin";

async function jsonOrThrow<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const body = await res.text();
    throw new Error(body || `HTTP ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export async function fetchMeta(): Promise<ProviderMeta> {
  const res = await fetch(`${BASE}/providers/meta`, { credentials: "include" });
  return jsonOrThrow<ProviderMeta>(res);
}

export async function fetchProviders(): Promise<Provider[]> {
  const res = await fetch(`${BASE}/providers`, { credentials: "include" });
  const data = await jsonOrThrow<{ providers: Provider[] }>(res);
  return data.providers;
}

export type CreateProviderInput = {
  name: string;
  protocol: string;
  base_url: string;
  api_key: string | null;
  voices?: Voice[];
  initial_capabilities?: string[];  // if omitted → probe auto-detects
};

export async function createProvider(input: CreateProviderInput): Promise<Provider> {
  const res = await fetch(`${BASE}/providers`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  const data = await jsonOrThrow<{ provider: Provider }>(res);
  return data.provider;
}

export type UpdateProviderInput = Partial<{
  name: string;
  base_url: string;
  api_key: string | null;
  capabilities: string[];
  voices: Voice[];
}>;

export async function updateProvider(
  id: number,
  patch: UpdateProviderInput,
): Promise<Provider> {
  const res = await fetch(`${BASE}/providers/${id}`, {
    method: "PATCH",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(patch),
  });
  const data = await jsonOrThrow<{ provider: Provider }>(res);
  return data.provider;
}

export async function deleteProvider(id: number): Promise<number> {
  const res = await fetch(`${BASE}/providers/${id}`, {
    method: "DELETE",
    credentials: "include",
  });
  const data = await jsonOrThrow<{ ok: boolean; routes_cleared: number }>(res);
  return data.routes_cleared;
}

export async function probeProvider(id: number): Promise<Provider> {
  const res = await fetch(`${BASE}/providers/${id}/probe`, {
    method: "POST",
    credentials: "include",
  });
  const data = await jsonOrThrow<{ provider: Provider }>(res);
  return data.provider;
}

export async function fetchAffectedFeatures(id: number): Promise<FeatureRoute[]> {
  const res = await fetch(`${BASE}/providers/${id}/affected-features`, {
    credentials: "include",
  });
  const data = await jsonOrThrow<{ affected: FeatureRoute[] }>(res);
  return data.affected;
}

export async function fetchRoutes(): Promise<FeatureRoute[]> {
  const res = await fetch(`${BASE}/feature-routes`, { credentials: "include" });
  const data = await jsonOrThrow<{ routes: FeatureRoute[] }>(res);
  return data.routes;
}

export type SetRouteInput = {
  provider_id: number | null;
  model_name: string | null;
  user_choices: number[] | null;
  provider_models?: Record<string, string>;
};

export async function setFeatureRoute(
  feature: Feature,
  input: SetRouteInput,
): Promise<FeatureRoute> {
  const res = await fetch(`${BASE}/feature-routes/${feature}`, {
    method: "PATCH",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  const data = await jsonOrThrow<{ route: FeatureRoute }>(res);
  return data.route;
}

export type FeatureTestResult = {
  status: "ok" | "error";
  error: string | null;
};

export async function testFeatureRoute(feature: Feature, providerId?: number): Promise<FeatureTestResult> {
  const url = providerId != null
    ? `${BASE}/feature-routes/${feature}/test?provider_id=${providerId}`
    : `${BASE}/feature-routes/${feature}/test`;
  const res = await fetch(url, { method: "POST", credentials: "include" });
  return jsonOrThrow<FeatureTestResult>(res);
}

export type DiscoverVoicesResult = {
  voices: Array<{ voice_id: string; name: string; language: string }>;
  discoverable: boolean;
};

export async function discoverVoices(
  baseUrl: string,
  apiKey?: string | null,
  voicesPath?: string | null,
): Promise<DiscoverVoicesResult> {
  const res = await fetch(`${BASE}/providers/discover-voices`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      base_url: baseUrl,
      api_key: apiKey,
      voices_path: voicesPath || null,
    }),
  });
  return jsonOrThrow<DiscoverVoicesResult>(res);
}

// ─── Export / Import / Clear ──────────────────────────────────────────────

export async function exportConfig(): Promise<{ blob: Blob; filename: string }> {
  const res = await fetch(`${BASE}/providers/export`, { credentials: "include" });
  if (!res.ok) {
    throw new Error((await res.text()) || `HTTP ${res.status}`);
  }
  const disposition = res.headers.get("Content-Disposition") || "";
  const match = /filename="?([^"]+)"?/.exec(disposition);
  const filename = match ? match[1] : `kis-ai-config-${new Date().toISOString().slice(0, 10)}.json`;
  const blob = await res.blob();
  return { blob, filename };
}

export async function importPreview(
  config: unknown,
): Promise<ImportPreviewResult> {
  const res = await fetch(`${BASE}/providers/import/preview`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ config }),
  });
  return jsonOrThrow<ImportPreviewResult>(res);
}

export async function importConfig(
  config: unknown,
): Promise<ImportResult> {
  const res = await fetch(`${BASE}/providers/import`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ config }),
  });
  return jsonOrThrow<ImportResult>(res);
}

export async function clearAllProviders(): Promise<ClearAllResult> {
  const res = await fetch(`${BASE}/providers/all`, {
    method: "DELETE",
    credentials: "include",
  });
  return jsonOrThrow<ClearAllResult>(res);
}

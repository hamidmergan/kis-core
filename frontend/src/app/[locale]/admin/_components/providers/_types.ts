export type Capability =
  | "chat"
  | "embedding"
  | "vision"
  | "ocr"
  | "stt"
  | "tts"
  | "image_gen"
  | "image_edit"
  | "translation";

export type Feature =
  | "chat"
  | "embedding"
  | "vision"
  | "ocr"
  | "stt"
  | "tts"
  | "image_gen"
  | "image_edit"
  | "doc_translate"
  | "screencast_translate"
  | "transcript_translate";

export type Protocol = string;

export type ProviderMeta = {
  protocols: Array<{ id: Protocol; fixed_capabilities: Capability[] }>;
  capabilities: Capability[];
  features: Feature[];
  user_choice_features: Feature[];
  api_key_encryption_enabled: boolean;
  concurrency_buckets: string[];
  fallback_features: Feature[];
};

export type Voice = {
  voice_id: string;
  name: string;
  language: string;       // required – e.g. "de", "en"
  description?: string;
};

export type Provider = {
  id: number;
  name: string;
  protocol: Protocol;
  base_url: string;
  capabilities: Capability[];
  voices: Voice[];
  enabled: boolean;
  last_probed_at: string | null;
  probe_status: string | null;
  probe_error: string | null;
  api_key_set: boolean;
  api_key_last_chars: string | null;
  // Simultaneous calls per bucket, a missing key means no cap.
  concurrency: Record<string, number>;
  created_at: string;
  updated_at: string;
};

/** What was measured on a model, source says how reliable it is. */
export type ModelLimits = {
  window_tokens: number;
  source: "gemessen" | "unbekannt" | "gelernt" | "gesetzt";
  thinks: boolean;
  think_off: string;
  context_chars: number;
  tool_context_chars: number;
};

/** The window of one provider and model, null when nothing is known. */
export type ModelWindow = {
  provider_id: number;
  model_name: string;
  window_tokens: number | null;
  source: ModelLimits["source"];
};

export type ModelWindows = {
  models: ModelWindow[];
  unmeasured_window_tokens: number;
};

// Temperatur und top_p je Anbieter, fehlender Wert heisst nichts mitsenden.
export type Sampling = { temperature?: number; top_p?: number };

export type FeatureRoute = {
  id: number;
  feature: Feature;
  provider_id: number | null;
  model_name: string | null;
  user_choices: number[];
  provider_models: Record<string, string>;
  provider_sampling: Record<string, Sampling>;
  // Derived from the order, the second usable provider, its model sits in provider_models.
  fallback_provider_id: number | null;
  // The providers in the admin's order, the first usable one is the standard.
  provider_order: number[];
  updated_at: string;
  limits?: ModelLimits | null;
};

// ─── Export / Import ──────────────────────────────────────────────────────

export type ImportPreviewProvider = {
  name: string;
  action: "create" | "update";
  needs_api_key: boolean;
  existing_has_key: boolean;
  protocol_change: { from: string; to: string } | null;
  encrypted_key_present: boolean;
  encrypted_key_recoverable: boolean;
};

export type ImportPreviewRoute =
  | { feature: string; action: "create" | "update"; resolved_provider: string }
  | { feature: string; action: "skip_unresolved"; reason: string };

export type ImportPreviewResult = {
  providers: ImportPreviewProvider[];
  routes: ImportPreviewRoute[];
};

export type ImportResult = {
  providers_created: number;
  providers_updated: number;
  routes_created: number;
  routes_updated: number;
  routes_skipped: number;
  providers_needing_key: string[];
};

export type ClearAllResult = {
  providers_deleted: number;
  routes_deleted: number;
};

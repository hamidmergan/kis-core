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
  last_probed_at: string | null;
  probe_status: string | null;
  probe_error: string | null;
  api_key_set: boolean;
  api_key_last_chars: string | null;
  created_at: string;
  updated_at: string;
};

export type FeatureRoute = {
  id: number;
  feature: Feature;
  provider_id: number | null;
  model_name: string | null;
  user_choices: number[];
  provider_models: Record<string, string>;
  updated_at: string;
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

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

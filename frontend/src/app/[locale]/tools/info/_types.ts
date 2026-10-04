export interface CampusQuelle {
  page_id: number;
  kind: "page" | "document" | "place";
  url: string | null;
  title: string;
  filename: string | null;
  /** Date of the last fetch as YYYY-MM-DD. */
  fetched_at: string | null;
  /** Verbatim start of the matching passage, for the browser's text fragment. */
  fragment: string | null;
}

export interface CampusOrt {
  id: string;
  code: string | null;
  title: { de?: string; en?: string };
  /** What the map's show parameter expects. */
  show: string;
}

export interface CampusNachricht {
  id?: number;
  role: "user" | "assistant";
  content: string;
  sources: CampusQuelle[];
  places: CampusOrt[];
  no_source?: boolean;
  failed?: boolean;
  /** True while the answer is still arriving. */
  streaming?: boolean;
  /** True once the backend sent its first event, which is when the search finished. */
  metaArrived?: boolean;
}

export interface CampusChatEintrag {
  id: number;
  title: string;
  question_count: number;
  created_at: string;
  updated_at: string;
}

export interface CampusConfig {
  map_url: string;
  retention_days: number;
  max_question_chars: number;
  max_questions_per_chat: number;
}

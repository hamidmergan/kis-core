export interface Source {
  uuid: string;
  filename: string;
  status: "pending" | "indexing" | "ready" | "failed";
  error_message?: string | null;
}

export type TranscriptTranslationMode = "off" | "auto" | "manual";

export interface WorkspaceDetail {
  uuid: string;
  title: string;
  description?: string | null;
  status: string;
  is_active: boolean;
  is_owner?: boolean;
  transcript_translation_mode?: TranscriptTranslationMode;
  sources: Source[];
}

export interface SourceRef {
  source_uuid: string;
  filename?: string;
  page_number: number;
  source_text?: string;
  start_time?: number;
  end_time?: number;
  is_popup_selection?: boolean;
}

export interface SourceQmap {
  qnum: number;
  uuid: string;
  filename: string;
  is_media?: boolean;
}

export interface ChatMessage {
  id?: string;
  role: "user" | "assistant";
  content: string;
  source_pages?: SourceRef[];
  source_qmap?: SourceQmap[];
  sourceCount?: number;
  popup_selection?: { uuid: string; page: number; text: string };
  aborted?: boolean;
}

export interface LernKarte {
  front: string;
  back: string;
}

export interface QuizQuestion {
  question: string;
  options: string[];
  correct: number;
}

export interface ViewerState {
  uuid: string;
  filename: string;
  page: number;
  highlightText?: string;
  // True when highlightText is a verbatim user-popup selection (highlight it
  // exactly, no line/sentence expansion). False/omitted for LLM-suggested
  // citations (expand to bullet/line for readable context).
  exactSelection?: boolean;
  nonce?: number;
  startTime?: number;
}

export interface DataTableRowSource {
  source_label: string;
  page: number | string;
  highlight?: string;
}

export interface DataTableData {
  title: string;
  columns: string[];
  rows: { cells: string[]; sources: number[] | DataTableRowSource[] }[];
}

export interface DataTableSource {
  number: number;
  filename: string;
}

export type StudioView = "overview" | "karteikarten" | "quiz" | "data_table" | "mindmap" | "notes";
export type PanelKey = "quellen" | "chat" | "studio";

export interface GlossaryEntry {
  id: number;
  term_de: string;
  term_en: string;
  definition: string;
  definition_en?: string;
  example_sentence?: string;
  example_sentence_en?: string;
  page_number?: number;
  start_time?: number | null;
  filename?: string;
}

export interface ClozeExercise {
  glossary_entry_id: number;
  sentence: string;
  answer: string;
  options: string[];
  page_number?: number;
}

export interface VocabTestQuestion {
  glossary_entry_id: number;
  question: string;
  options: string[];
  correct_index: number;
  explanation?: string;
}

export type LanguageTrainingView = "overview" | "karteikarten" | "lueckentext" | "vokabeltest"
  | "lk-sets" | "lk-learn" | "lk-complete"
  | "cl-sets" | "cl-learn" | "cl-complete"
  | "vt-sets" | "vt-learn" | "vt-complete"
  | "create-set";

export interface ExerciseItemSource {
  source_label: string;
  page_number?: number;
  start_time?: number;
  highlight_text?: string;
}

export interface ExerciseItemExtras {
  word_parts?: string;
  word_parts_explained?: string;
  example_sentence?: string;
}

export interface ExerciseItem {
  id: number;
  set_id: number;
  position: number;
  front: string;
  back: string;
  back_en?: string;
  options?: string[];
  correct_idx?: number;
  source_label?: string;
  page_number?: number;
  start_time?: number;
  explanation?: string;
  sources?: ExerciseItemSource[];
  extras?: ExerciseItemExtras;
}

export interface ExerciseSet {
  id: number;
  workspace_id: number;
  user_id: number;
  tool: string;
  title: string;
  mode: string;
  source_uuid?: string;
  card_count: number;
  status?: string;
  created_at: string;
  total_attempts?: number;
  progress_pct?: number;
  last_run_correct?: number;
  items?: ExerciseItem[];
}

export interface StreakInfo {
  current_streak: number;
  max_streak: number;
  last_active_date: string | null;
}

export interface ExerciseOverview {
  total_sets: number;
  total_cards: number;
  total_attempts: number;
  total_correct: number;
  accuracy: number;
}

export interface HeatmapDay {
  day: string;
  answers: number;
  correct: number;
  wrong: number;
  sets_practiced: number;
}

export interface StudentStats {
  streak: StreakInfo;
  overview: ExerciseOverview;
  lerntools: ExerciseOverview;
  language_training: ExerciseOverview;
  heatmap: HeatmapDay[];
  lerntools_heatmap: HeatmapDay[];
  language_training_heatmap: HeatmapDay[];
  chat: { total: number; today: number };
  first_activity: string | null;
  active_days: number;
  today: string;
}

export type ScheduleEntryType = "deadline" | "termin";
export type ScheduleEntryOrigin = "llm" | "manual";

export interface ScheduleSourceRef {
  source_uuid: string;
  page_number: number | null;
  start_time: number | null;
  raw_quote: string | null;
}

export interface ScheduleEntry {
  id: number;
  type: ScheduleEntryType;
  title: string;
  description: string | null;
  due_date: string | null;   // 'YYYY-MM-DD'
  due_time: string | null;   // 'HH:MM'
  is_optional: boolean;
  is_checked: boolean;
  checked_at: string | null;
  origin: ScheduleEntryOrigin;
  source_refs: ScheduleSourceRef[];
  created_at: string | null;
  updated_at: string | null;
}

export interface ScheduleData {
  entries: ScheduleEntry[];
  processed_source_uuids: string[];
}

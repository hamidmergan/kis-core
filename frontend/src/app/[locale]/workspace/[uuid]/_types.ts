export type IndexingStage =
  | "parsing"
  | "ocr"
  | "chunking"
  | "embedding"
  | "summarizing";

export interface IndexingProgress {
  stage: IndexingStage;
  page?: number;
  total?: number;
}

/** How text recognition went, open pages can be caught up on. */
export interface OcrInfo {
  enabled: boolean;
  done: number;
  open: number[];
}

export interface Source {
  uuid: string;
  filename: string;
  status: "pending" | "indexing" | "ready" | "failed";
  error_message?: string | null;
  progress?: IndexingProgress | null;
  ocr_info?: OcrInfo | null;
  /** Chapter the source sits in within the list, null means no chapter. */
  chapter_uuid?: string | null;
  /** The link a web page source came from, empty for uploaded files. */
  source_url?: string | null;
  /** How the source came in, "text" marks a pasted text that can be edited. */
  file_type?: string;
  /** Whether a summary exists, the text itself is fetched when opened. */
  has_summary?: boolean;
}

/** Chapters only structure the display, the selection hangs off the file's checkbox. */
export interface Chapter {
  uuid: string;
  name: string;
  position: number;
}

// The target languages come from the backend.

// Plain name for a language code, the upper-cased code when in doubt.
export function langLabel(code: string, locale: string): string {
  try {
    const name = new Intl.DisplayNames([locale], { type: "language" }).of(code);
    if (name) return name.charAt(0).toUpperCase() + name.slice(1);
  } catch { /* Intl.DisplayNames unavailable or bad code */ }
  return code.toUpperCase();
}

export interface StaffNoteLink {
  url: string;
  label: string;
}

export interface WorkspaceDetail {
  uuid: string;
  title: string;
  description?: string | null;
  status: string;
  is_active: boolean;
  is_owner?: boolean;
  /** Owner or tutor. Drives the UI, is_owner is literal ownership only. */
  can_manage?: boolean;
  /** Demo course: enrolled people may preview the owner layout here, read only. */
  is_demo_workspace?: boolean;
  /** The one demo course the guided tour runs in. */
  is_tour_module?: boolean;
  transcript_target_lang?: string;
  /** Language the CEFR chat diagnosis is held in (ISO code, default "de"). */
  diagnosis_language?: string;
  /** Text recognition on at all, otherwise the catch-up is dropped. */
  ocr_enabled?: boolean;
  /** Longest pasted text a text source may hold. */
  text_source_max_chars?: number;
  staff_note_text?: string | null;
  staff_note_links?: StaffNoteLink[];
  chapters?: Chapter[];
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
  action_key?: string;
  action_icon?: string;
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
  popup_selection?: { uuid: string; page: number; text: string; action_key?: string; action_icon?: string };
  aborted?: boolean;
  /** Stream died on an error (not a user cancellation) — the turn offers a retry. */
  failed?: boolean;
  /** Applied level, for admins only as a small grey line. */
  applied_level?: string | null;
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
  // Text to highlight verbatim, only from the selection bar, never from a chip.
  highlightText?: string;
  // True when the text is highlighted verbatim instead of expanded to sentence bounds.
  exactSelection?: boolean;
  // Hides the transcript so listening comprehension does not become reading along.
  hideTranscript?: boolean;
  // True when a citation chip opened the viewer.
  isCitation?: boolean;
  nonce?: number;
  startTime?: number;
  // End of the cited spot, not of a single subtitle line.
  endTime?: number;
  // Start of the cited section, needed when the guess in startTime does not hold.
  chunkStart?: number;
  // The part of the answer the chip backs, marks the passage on a page or the lines of a span.
  citationClaim?: string;
  // Set for a YouTube source, the viewer embeds the video instead of streaming a file.
  youtubeId?: string;
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
  base_form?: string;
  definition: string;
  definition_en?: string;
  example_sentence?: string;
  example_sentence_en?: string;
  page_number?: number;
  start_time?: number | null;
  filename?: string;
}

/** One entry of the grammar exercise catalogue, as the backend exposes it. */
/** A grammar topic of the course, the name is all the teacher types. */
export interface GrammarTopic {
  id: number;
  name: string;
  created_by?: number | null;
  // Fixed formats set by staff, empty means free choice.
  kinds?: string[] | null;
}

/** Result of marking one free-text grammar answer. */
export interface GrammarCheckResult {
  verdict: "correct" | "close" | "wrong";
  solution: string;
  explanation?: string | null;
}

export type LanguageTrainingView = "overview"
  | "lk-sets" | "lk-learn"
  | "gr-sets" | "gr-learn" | "gr-complete"
  | "wo-sets" | "wo-learn" | "wo-complete";

/** One entry of a set's source legend: the number the chips print, and the file. */
export interface ExerciseSetSource {
  number: number;
  filename: string;
}

export interface ExerciseItemSource {
  source_label: string;
  page_number?: number;
  start_time?: number;
  highlight_text?: string;
}

export interface ExerciseItemExtras {
  /** Pattern pair of the reshaping, on the exercise because mixed sets share none. */
  pattern_front?: string;
  pattern_back?: string;
  /** The hint for the exercise, without it the button asks the chat. */
  tip?: string;
  word_parts?: string;
  word_parts_explained?: string;
  example_sentence?: string;
  word_class?: string;
  singular?: string;
  plural?: string;
  /** Verb forms of the three tenses, either all or none. */
  verb_present?: string;
  verb_past?: string;
  verb_perfect?: string;
  /** Fixed preposition of a verb with its case, e.g. "über + Akk.". */
  verb_preposition?: string;
  /** Per gap the base form as a chip and the fitting form, in the order of the text. */
  gaps?: { base: string; solution: string }[];
  /** Instruction and solved example sit on the exercise because the pool holds exercises only. */
  instruction?: string;
  example?: { gapped: string; solved: string };
  /** Set title, only needed when completing a pool row. */
  title?: string;
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
  /** The sources of the set in the order they were picked, empty in the glossary. */
  sources?: ExerciseSetSource[];
  card_count: number;
  status?: string;
  created_at: string;
  total_attempts?: number;
  /** Share of cards whose last answer was correct, the ring on the card. */
  progress_pct?: number;
  items?: ExerciseItem[];
  // Grammar sets only: the catalogue entry plus the header shown above the sentences.
  grammar_type?: string | null;
  /** Localised name of the catalogue entry, list view only. */
  grammar_topic_name?: string | null;
  instruction?: string | null;
  pattern_front?: string | null;
  pattern_back?: string | null;
  /** The person's own instruction to the tool, not the grammar task line above. */
  user_instruction?: string | null;
  /** The instruction named something the sources do not cover, the set used everything. */
  instruction_unmatched?: boolean;
  /** Whether a voice is set up, only delivered with the single set. */
  speech_enabled?: boolean;
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
  /** When set, the appointment runs until this day. */
  end_date: string | null;
  due_time: string | null;   // 'HH:MM'
  /** When set, it ends on its day at this time. */
  end_time: string | null;
  /** Start known, end explicitly open, it is never greyed out. */
  is_open_ended?: boolean;
  /** With 'month' the source named only the month and the view shows no day. */
  date_precision?: "day" | "month" | null;
  /** The source wrote no year, the system picked the nearest one. */
  year_assumed?: boolean;
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

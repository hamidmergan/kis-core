export type IndexingStage =
  | "parsing"
  | "ocr"
  | "chunking"
  | "embedding";

export interface IndexingProgress {
  stage: IndexingStage;
  page?: number;
  total?: number;
}

export interface Source {
  uuid: string;
  filename: string;
  status: "pending" | "indexing" | "ready" | "failed";
  error_message?: string | null;
  progress?: IndexingProgress | null;
}

// The list of target languages comes from the backend (GET /ai-assistant/
// transcript-languages, single source: i18n.TRANSCRIPT_LANGUAGES). Viewer tabs
// label arbitrary detected source codes via langLabel below.

// Human label for an ISO language code in the user's locale, e.g. langLabel("fr","de")
// -> "Französisch". Falls back to the upper-cased code when the runtime can't resolve it.
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
  transcript_target_lang?: string;
  /** Language the CEFR chat diagnosis is held in (ISO code, default "de"). */
  diagnosis_language?: string;
  /** Sprachtrainer switched on for this workspace by its owner, admin switch included. */
  language_training_active?: boolean;
  /** Sprachtrainer offered on this platform at all (admin setting, off by default). */
  language_training_enabled?: boolean;
  staff_note_text?: string | null;
  staff_note_links?: StaffNoteLink[];
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
  /** CEFR level the adaptive tutor applied to this answer, or null when none was
   *  applied. Shown to admins only as a small grey label. */
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
  // Verbatim text to highlight on the page. Only set by a popup/action-bar exact
  // selection (the user marked this text). Citation chips never set it — a chip
  // click only scrolls to the page/timestamp.
  highlightText?: string;
  // True when highlightText is a verbatim user-popup selection (highlight it
  // exactly, no line/sentence expansion). Always true when highlightText is set,
  // since the only remaining highlight source is the popup exact selection.
  exactSelection?: boolean;
  // Blendet das Transkript im Quellen-Fenster aus. Gesetzt vom Hör- und
  // Leseverstehen: wer beim Hören mitlesen kann, hört nicht zu, und die Aufgabe
  // prüft wieder Lesen. Der Aufgabenkasten zeigt deshalb keinen Text UND das
  // Quellen-Fenster auch nicht.
  hideTranscript?: boolean;
  // True when the viewer was opened by clicking a citation chip (pill / source
  // reference) — used only to distinguish a chip nav from a plain document open.
  isCitation?: boolean;
  nonce?: number;
  startTime?: number;
  // End of the CITED passage, not of a single subtitle cue. A retrieval chunk runs some
  // 45 seconds and therefore spans several cues, so marking only the cue at startTime
  // leaves the rest of the cited passage unmarked — the sentence the answer rests on
  // often sits in the second or third cue and reads as "not in the source". With the end
  // the transcript marks the whole span.
  endTime?: number;
  // The piece of the ANSWER this chip backs up. The marked span runs about a minute, so the
  // transcript uses this to weight the line carrying the claim over the rest of the span.
  // Ranking among lines already known to be right, never a search.
  citationClaim?: string;
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
/** Ein Grammatikthema des Kurses. Der Name ist alles, was der Dozent tippt. */
export interface GrammarTopic {
  id: number;
  name: string;
  created_by?: number | null;
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
  | "hv-sets" | "hv-learn";

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
  /** Musterpaar der Grammatik-Übung, nur bei einer Umformung gesetzt. Es hängt an
   *  der Aufgabe, weil ein gemischtes Set kein gemeinsames Muster mehr hat. */
  pattern_front?: string;
  pattern_back?: string;
  word_parts?: string;
  word_parts_explained?: string;
  example_sentence?: string;
  word_class?: string;
  singular?: string;
  plural?: string;
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
  /** The set's sources, numbered in the order the learner picked them. The citation
   *  chips print these numbers, so they are the same on every item of the set.
   *  Empty in glossary mode. */
  sources?: ExerciseSetSource[];
  card_count: number;
  status?: string;
  created_at: string;
  total_attempts?: number;
  /** Anteil der Karten, deren letzte Antwort richtig war. Der Ring auf der Karte. */
  progress_pct?: number;
  items?: ExerciseItem[];
  // Grammar sets only: the catalogue entry plus the header shown above the sentences.
  grammar_type?: string | null;
  /** Localised name of the catalogue entry, e.g. "Passiv Präsens". List view only. */
  grammar_topic_name?: string | null;
  instruction?: string | null;
  pattern_front?: string | null;
  pattern_back?: string | null;
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

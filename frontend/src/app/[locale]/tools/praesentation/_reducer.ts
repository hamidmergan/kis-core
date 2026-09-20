import { stepIndex } from "./_logic";
import type { JobProgress, JobStatus, Language, Outline, OutlineRow, PraesentationState, Slide, Source, Step } from "./_types";

export const INITIAL_STATE: PraesentationState = {
  step: "content",
  maxReached: 0,
  source: { mode: "files", files: [], moduleId: "", sourceIds: [] },
  instructions: "",
  language: "de",
  notes: false,
  notesInclude: true,
  templateId: "thl",
  jobUuid: null,
  jobStatus: "idle",
  progress: null,
  error: "",
  outline: null,
  slides: [],
  previews: {},
  missingImages: [],
  hasDeck: false,
  templateFallback: false,
  starting: false,
};

export type Action =
  | { type: "RESTORE"; state: Partial<PraesentationState> }
  | { type: "RESET" }
  | { type: "GO"; step: Step }
  | { type: "SET_SOURCE"; source: Partial<Source> }
  | { type: "SET_INSTRUCTIONS"; text: string }
  | { type: "SET_LANGUAGE"; language: Language }
  | { type: "SET_NOTES"; notes: boolean }
  | { type: "SET_NOTES_INCLUDE"; include: boolean }
  | { type: "SET_TEMPLATE"; templateId: string }
  | { type: "STARTING" }
  | { type: "STARTED"; jobUuid: string }
  | { type: "JOB"; status: JobStatus; progress: JobProgress | null; error?: string | null }
  | { type: "VIEW"; outline: Outline | null; slides: Slide[]; previews: string[]; missingImages: string[]; hasDeck: boolean; templateFallback: boolean; bump?: boolean }
  | { type: "UPDATE_ROW"; row: OutlineRow }
  | { type: "MOVE_ROW"; id: string; delta: -1 | 1 }
  | { type: "DELETE_ROW"; id: string }
  | { type: "ADD_ROW"; title: string }
  | { type: "UPDATE_SLIDE"; slide: Slide }
  | { type: "MOVE_SLIDE"; id: string; delta: -1 | 1 }
  | { type: "DELETE_SLIDE"; id: string }
  | { type: "PREVIEW_FRESH"; id: string }
  | { type: "FAIL"; error: string };

const enter = (state: PraesentationState, step: Step): PraesentationState =>
  ({ ...state, step, maxReached: Math.max(state.maxReached, stepIndex(step)) });

function move<T extends { id: string }>(list: T[], id: string, delta: -1 | 1): T[] {
  const i = list.findIndex((x) => x.id === id);
  const j = i + delta;
  if (i < 0 || j < 0 || j >= list.length) return list;
  const out = [...list];
  [out[i], out[j]] = [out[j], out[i]];
  return out;
}

export function reducer(state: PraesentationState, action: Action): PraesentationState {
  switch (action.type) {
    case "RESTORE":
      return { ...state, ...action.state };
    case "RESET":
      return INITIAL_STATE;
    case "GO":
      return enter(state, action.step);
    case "SET_SOURCE":
      return { ...state, source: { ...state.source, ...action.source } };
    case "SET_INSTRUCTIONS":
      return { ...state, instructions: action.text };
    case "SET_LANGUAGE":
      return { ...state, language: action.language };
    case "SET_NOTES":
      return { ...state, notes: action.notes };
    case "SET_NOTES_INCLUDE":
      return { ...state, notesInclude: action.include };
    case "SET_TEMPLATE":
      return { ...state, templateId: action.templateId };
    case "STARTING":
      return { ...enter(state, "slides"), starting: true, error: "", outline: null, slides: [], previews: {}, progress: null,
               missingImages: [], hasDeck: false, templateFallback: false };
    case "STARTED":
      return { ...state, jobUuid: action.jobUuid, jobStatus: "pending", starting: false };
    case "JOB": {
      const next = { ...state, jobStatus: action.status, progress: action.progress, starting: false };
      // A stale error must not survive a resume that is now running or already done again.
      next.error = action.error || (action.status === "failed" || action.status === "paused" ? state.error : "");
      if (action.status === "success") return enter(next, "done");
      return next;
    }
    case "VIEW": {
      const previews = { ...state.previews };
      // A finished job bumps every kept version so the browser refetches instead of showing a cached preview.
      for (const id of action.previews) previews[id] = action.bump ? (previews[id] ?? 0) + 1 : previews[id] ?? 1;
      for (const id of Object.keys(previews)) if (!action.previews.includes(id)) delete previews[id];
      return { ...state, outline: action.outline, slides: action.slides, previews, missingImages: action.missingImages,
               hasDeck: action.hasDeck, templateFallback: action.templateFallback };
    }
    case "UPDATE_ROW":
      if (!state.outline) return state;
      return { ...state, outline: { ...state.outline, rows: state.outline.rows.map((r) => (r.id === action.row.id ? action.row : r)) } };
    case "MOVE_ROW":
      if (!state.outline) return state;
      return { ...state, outline: { ...state.outline, rows: move(state.outline.rows, action.id, action.delta) } };
    case "DELETE_ROW":
      if (!state.outline) return state;
      return { ...state, outline: { ...state.outline, rows: state.outline.rows.filter((r) => r.id !== action.id) } };
    case "ADD_ROW": {
      if (!state.outline) return state;
      // Before the closing slide, with a placeholder id the server replaces on save.
      const rows = [...state.outline.rows];
      const neu: OutlineRow = { id: `neu${rows.length}`, role: "text", title: action.title, gist: "" };
      rows.splice(Math.max(rows.length - 1, 0), 0, neu);
      return { ...state, outline: { ...state.outline, rows } };
    }
    case "UPDATE_SLIDE":
      return { ...state, slides: state.slides.map((s) => (s.id === action.slide.id ? action.slide : s)) };
    case "MOVE_SLIDE":
      return { ...state, slides: move(state.slides, action.id, action.delta) };
    case "DELETE_SLIDE":
      return { ...state, slides: state.slides.filter((s) => s.id !== action.id) };
    case "PREVIEW_FRESH":
      return { ...state, previews: { ...state.previews, [action.id]: (state.previews[action.id] ?? 0) + 1 } };
    case "FAIL":
      return { ...state, error: action.error, starting: false };
    default:
      return state;
  }
}

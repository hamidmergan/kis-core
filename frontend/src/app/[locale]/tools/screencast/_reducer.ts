import type { ScreencastStep, SlideData } from "@/types";

export interface ScreencastFlowState {
  step: ScreencastStep;
  loading: boolean;
  errorMessage: string;
  slides: SlideData[];
  translateJobUuid: string;
  maxReachedIdx: number;
  correctedFileName: string | null;
  lightboxIndex: number | null;
  isResumedJob: boolean;
}

export const INITIAL_FLOW_STATE: ScreencastFlowState = {
  step: "upload",
  loading: false,
  errorMessage: "",
  slides: [],
  translateJobUuid: "",
  maxReachedIdx: 0,
  correctedFileName: null,
  lightboxIndex: null,
  isResumedJob: false,
};

export type FlowAction =
  | { type: "RESET" }
  | { type: "SET_STEP"; step: ScreencastStep }
  | { type: "SET_LOADING"; loading: boolean }
  | { type: "GO_ERROR"; message: string }
  | { type: "SET_ERROR_MESSAGE"; message: string }
  | { type: "SET_SLIDES"; slides: SlideData[] }
  | { type: "UPDATE_SLIDE_SCRIPT"; index: number; script: string }
  | { type: "CLEAR_SCRIPTS" }
  | { type: "IMPORT_SCRIPTS"; scripts: string[] }
  | { type: "BACKFILL_IMAGES"; images: string[] }
  | { type: "SET_JOB_UUID"; uuid: string }
  | { type: "SET_CORRECTED_FILENAME"; name: string | null }
  | { type: "SET_LIGHTBOX"; index: number | null }
  | { type: "SET_RESUMED"; resumed: boolean }
  | { type: "ADVANCE_REACHED"; idx: number }
  | { type: "ENTER_STEP"; step: ScreencastStep; loading?: boolean }
  | {
      type: "RESUME";
      jobUuid: string;
      slides: SlideData[];
      step: ScreencastStep;
      stepIdx: number;
    };

export function flowReducer(state: ScreencastFlowState, action: FlowAction): ScreencastFlowState {
  switch (action.type) {
    case "RESET":
      return INITIAL_FLOW_STATE;
    case "SET_STEP":
      return { ...state, step: action.step };
    case "SET_LOADING":
      return { ...state, loading: action.loading };
    case "GO_ERROR":
      return { ...state, errorMessage: action.message, step: "error", loading: false };
    case "SET_ERROR_MESSAGE":
      return { ...state, errorMessage: action.message };
    case "SET_SLIDES":
      return { ...state, slides: action.slides };
    case "UPDATE_SLIDE_SCRIPT":
      return {
        ...state,
        slides: state.slides.map((s, i) => (i === action.index ? { ...s, script: action.script } : s)),
      };
    case "CLEAR_SCRIPTS":
      return { ...state, slides: state.slides.map((s) => ({ ...s, script: "" })) };
    case "IMPORT_SCRIPTS":
      return {
        ...state,
        slides: state.slides.map((s, i) => ({ ...s, script: action.scripts[i] ?? "" })),
      };
    case "BACKFILL_IMAGES":
      return {
        ...state,
        slides: state.slides.map((s, i) => ({ ...s, imageBase64: action.images[i] ?? s.imageBase64 })),
      };
    case "SET_JOB_UUID":
      return { ...state, translateJobUuid: action.uuid };
    case "SET_CORRECTED_FILENAME":
      return { ...state, correctedFileName: action.name };
    case "SET_LIGHTBOX":
      return { ...state, lightboxIndex: action.index };
    case "SET_RESUMED":
      return { ...state, isResumedJob: action.resumed };
    case "ADVANCE_REACHED":
      return { ...state, maxReachedIdx: Math.max(state.maxReachedIdx, action.idx) };
    case "ENTER_STEP":
      return { ...state, step: action.step, loading: action.loading ?? state.loading };
    case "RESUME":
      return {
        ...state,
        translateJobUuid: action.jobUuid,
        isResumedJob: true,
        slides: action.slides.length ? action.slides : state.slides,
        step: action.step,
        maxReachedIdx: action.stepIdx,
      };
  }
}

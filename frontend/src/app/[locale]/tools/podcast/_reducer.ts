import { stepIndex } from "./_logic";
import {
  ROLES,
  type JobProgress,
  type JobStatus,
  type Language,
  type Length,
  type Line,
  type Person,
  type PersonCount,
  type PodcastState,
  type Source,
  type Step,
  type Style,
} from "./_types";

const NAMES = ["Lena", "Jonas", "Amira", "Tom"] as const;

export const defaultPersons = (): Person[] => ROLES.map((role, i) => ({ name: NAMES[i], role, voiceId: "", providerId: 0 }));

export const INITIAL_STATE: PodcastState = {
  step: "content",
  maxReached: 0,
  source: { mode: "files", files: [], moduleId: "", sourceIds: [] },
  instructions: "",
  language: "de",
  count: 2,
  persons: defaultPersons(),
  length: "medium",
  style: "teaching",
  // No tempo slider any more, a voice slowed down by the provider echoes.
  speed: 1,
  jobUuid: null,
  jobStatus: "idle",
  progress: null,
  error: "",
  lines: [],
  selfWritten: false,
  instructionUnmatched: false,
  voicedIds: [],
  seconds: null,
  starting: false,
};

export type Action =
  | { type: "RESTORE"; state: Partial<PodcastState> }
  | { type: "RESET" }
  | { type: "GO"; step: Step }
  | { type: "SET_SOURCE"; source: Partial<Source> }
  | { type: "SET_INSTRUCTIONS"; text: string }
  | { type: "SET_LANGUAGE"; language: Language }
  | { type: "SET_COUNT"; count: PersonCount }
  | { type: "SET_PERSON"; index: number; person: Partial<Person> }
  | { type: "SET_LENGTH"; length: Length }
  | { type: "SET_STYLE"; style: Style }
  | { type: "SET_SPEED"; speed: number }
  | { type: "STARTING" }
  | { type: "STARTED"; jobUuid: string }
  | { type: "JOB"; status: JobStatus; progress: JobProgress | null; error?: string | null; seconds?: number | null }
  | { type: "LINES"; lines: Line[]; voicedIds?: string[] }
  | { type: "UPDATE_LINE"; id: string; text: string }
  | { type: "SET_SPEAKER"; id: string; speaker: number }
  | { type: "DELETE_LINE"; id: string }
  | { type: "ADD_LINE" }
  | { type: "FAIL"; error: string };

const enter = (state: PodcastState, step: Step): PodcastState => ({
  ...state,
  step,
  maxReached: Math.max(state.maxReached, stepIndex(step)),
});

/** An edited contribution loses its audio, that is what makes the next run short. */
const ohneTon = (voicedIds: string[], id: string) => voicedIds.filter((v) => v !== id);

export function reducer(state: PodcastState, action: Action): PodcastState {
  switch (action.type) {
    case "RESTORE":
      return { ...state, ...action.state };
    case "RESET":
      return { ...INITIAL_STATE, persons: defaultPersons() };
    case "GO":
      return enter(state, action.step);
    case "SET_SOURCE":
      return { ...state, source: { ...state.source, ...action.source } };
    case "SET_INSTRUCTIONS":
      return { ...state, instructions: action.text };
    case "SET_LANGUAGE":
      return { ...state, language: action.language };
    case "SET_COUNT":
      return { ...state, count: action.count };
    case "SET_PERSON":
      return { ...state, persons: state.persons.map((p, i) => (i === action.index ? { ...p, ...action.person } : p)) };
    case "SET_LENGTH":
      return { ...state, length: action.length };
    case "SET_STYLE":
      return { ...state, style: action.style };
    case "SET_SPEED":
      return { ...state, speed: action.speed };
    case "STARTING":
      return { ...enter(state, "script"), starting: true, error: "", lines: [], voicedIds: [], progress: null, seconds: null };
    case "STARTED":
      return { ...state, starting: false, jobUuid: action.jobUuid, jobStatus: "pending" };
    case "JOB": {
      const next = { ...state, jobStatus: action.status, progress: action.progress, starting: false };
      if (action.error) next.error = action.error;
      if (action.seconds != null) next.seconds = action.seconds;
      if (action.status === "success") return enter(next, "done");
      return next;
    }
    case "LINES":
      return { ...state, lines: action.lines, voicedIds: action.voicedIds ?? state.voicedIds };
    case "UPDATE_LINE":
      return {
        ...state,
        lines: state.lines.map((l) => (l.id === action.id ? { ...l, text: action.text } : l)),
        voicedIds: ohneTon(state.voicedIds, action.id),
      };
    case "SET_SPEAKER": {
      // A person outside the cast has no voice, so that move is simply not made.
      if (action.speaker < 0 || action.speaker >= state.count) return state;
      return {
        ...state,
        lines: state.lines.map((l) => (l.id === action.id ? { ...l, speaker: action.speaker } : l)),
        voicedIds: ohneTon(state.voicedIds, action.id),
      };
    }
    case "DELETE_LINE":
      return {
        ...state,
        lines: state.lines.filter((l) => l.id !== action.id),
        voicedIds: ohneTon(state.voicedIds, action.id),
      };
    case "ADD_LINE": {
      const last = state.lines[state.lines.length - 1];
      const speaker = last ? (last.speaker + 1) % state.count : 0;
      // The server hands out the real id on save, this one only holds the place.
      return { ...state, lines: [...state.lines, { id: `neu${state.lines.length}`, speaker, text: "" }] };
    }
    case "FAIL":
      return { ...state, starting: false, jobStatus: "failed", error: action.error };
  }
}

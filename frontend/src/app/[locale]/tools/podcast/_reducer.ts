import { nextTick, rephrase, stepIndex } from "./_logic";
import { DEFAULT_NAMES } from "./_samples";
import {
  ROLES,
  type Language,
  type Length,
  type Line,
  type Person,
  type PersonCount,
  type PodcastState,
  type Run,
  type Source,
  type Step,
  type Style,
} from "./_types";

export const defaultPersons = (): Person[] => ROLES.map((role, i) => ({ name: DEFAULT_NAMES[i], role, voiceId: "" }));

const IDLE_RUN: Run = { status: "idle", failedId: null, failedOnce: false, voicedThisRun: 0, keptIds: [], cancelled: false };

export const INITIAL_STATE: PodcastState = {
  step: "content",
  maxReached: 0,
  source: { mode: "text", text: "", files: [], moduleId: "", sourceIds: [] },
  instructions: "",
  language: "de",
  count: 2,
  persons: defaultPersons(),
  length: "medium",
  style: "teaching",
  generating: false,
  lines: [],
  run: IDLE_RUN,
};

export type Action =
  | { type: "LOAD"; state: PodcastState }
  | { type: "RESET" }
  | { type: "GO"; step: Step }
  | { type: "SET_SOURCE"; source: Partial<Source> }
  | { type: "SET_INSTRUCTIONS"; text: string }
  | { type: "SET_LANGUAGE"; language: Language }
  | { type: "SET_COUNT"; count: PersonCount }
  | { type: "SET_PERSON"; index: number; person: Partial<Person> }
  | { type: "SET_LENGTH"; length: Length }
  | { type: "SET_STYLE"; style: Style }
  | { type: "GENERATE_START" }
  | { type: "GENERATE_DONE"; lines: Line[] }
  | { type: "UPDATE_LINE"; id: string; text: string }
  | { type: "REPHRASE_LINE"; id: string }
  | { type: "DELETE_LINE"; id: string }
  | { type: "ADD_LINE" }
  | { type: "START_VOICING" }
  | { type: "TICK" }
  | { type: "RESUME" }
  | { type: "CANCEL" };

const enter = (state: PodcastState, step: Step): PodcastState => ({
  ...state,
  step,
  maxReached: Math.max(state.maxReached, stepIndex(step)),
});

export function reducer(state: PodcastState, action: Action): PodcastState {
  switch (action.type) {
    case "LOAD":
      return action.state;
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
    case "GENERATE_START":
      // A new script starts over, old audio belongs to old lines.
      return { ...enter(state, "script"), generating: true, lines: [], run: { ...IDLE_RUN, failedOnce: state.run.failedOnce } };
    case "GENERATE_DONE":
      return { ...state, generating: false, lines: action.lines };
    case "UPDATE_LINE":
      return { ...state, lines: state.lines.map((l) => (l.id === action.id ? { ...l, text: action.text } : l)) };
    case "REPHRASE_LINE":
      return { ...state, lines: state.lines.map((l) => (l.id === action.id ? { ...l, text: rephrase(l.text) } : l)) };
    case "DELETE_LINE":
      return { ...state, lines: state.lines.filter((l) => l.id !== action.id) };
    case "ADD_LINE": {
      const last = state.lines[state.lines.length - 1];
      const speaker = last ? (last.speaker + 1) % state.count : 0;
      const id = `l${Date.now().toString(36)}${state.lines.length.toString(36)}`;
      return { ...state, lines: [...state.lines, { id, speaker, text: "", audioOf: null }] };
    }
    case "START_VOICING":
      return {
        ...enter(state, "voicing"),
        run: {
          status: "running",
          failedId: null,
          failedOnce: state.run.failedOnce,
          voicedThisRun: 0,
          keptIds: state.lines.filter((l) => l.audioOf === l.text).map((l) => l.id),
          cancelled: false,
        },
      };
    case "TICK": {
      if (state.run.status !== "running") return state;
      const tick = nextTick(state.lines, state.run);
      if (tick.kind === "done") return { ...enter(state, "done"), run: { ...state.run, status: "done" } };
      if (tick.kind === "fail") return { ...state, run: { ...state.run, status: "failed", failedId: tick.id, failedOnce: true } };
      return { ...state, lines: tick.lines, run: { ...state.run, voicedThisRun: state.run.voicedThisRun + 1 } };
    }
    case "RESUME":
      return { ...state, run: { ...state.run, status: "running", failedId: null } };
    case "CANCEL":
      // What is voiced stays voiced, only the run stops.
      return { ...state, step: "script", run: { ...IDLE_RUN, failedOnce: state.run.failedOnce, cancelled: true } };
  }
}

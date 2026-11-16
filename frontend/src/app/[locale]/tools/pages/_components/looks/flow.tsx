import type { Looks } from "./registry";
import { CYCLE } from "./flow-cycle";
import { LEVELS } from "./flow-levels";
import { STEPS } from "./flow-steps";
import { TIMELINE } from "./flow-timeline";
import { TREE } from "./flow-tree";
import "./flow.css";

/** The looks of everything that runs in an order or hangs in a structure, one file per kind. */
export const LOOKS_FLOW: Looks = { steps: STEPS, cycle: CYCLE, timeline: TIMELINE, tree: TREE, levels: LEVELS };

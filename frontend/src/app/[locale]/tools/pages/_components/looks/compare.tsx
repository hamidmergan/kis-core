import type { Looks } from "./registry";
import { EXAMPLE } from "./compare-example";
import { FORMULA, HIGHLIGHT } from "./compare-formula";
import { MATRIX } from "./compare-matrix";
import { MISTAKES } from "./compare-mistakes";
import { VENN } from "./compare-venn";
import { VERSUS } from "./compare-versus";
import "./compare.css";

/** Comparisons, formulas, mistakes and examples, one file per kind. */
export const LOOKS_COMPARE: Looks = {
  versus: VERSUS, matrix: MATRIX, venn: VENN, formula: FORMULA, mistakes: MISTAKES, example: EXAMPLE, highlight: HIGHLIGHT,
};

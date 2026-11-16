import type { Looks } from "./registry";
import { BARS } from "./numbers-bars";
import { CHART } from "./numbers-chart";
import { FIGURES } from "./numbers-figures";
import { SCALE } from "./numbers-scale";
import { TABLE } from "./numbers-table";
import "./numbers.css";

/** Figures, bars, charts, tables and scales, one file per kind. */
export const LOOKS_NUMBERS: Looks = { figures: FIGURES, bars: BARS, chart: CHART, table: TABLE, scale: SCALE };

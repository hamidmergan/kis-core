/** A value as the looks draw it: never negative, anything that is no number counts as zero. */
export const val = (v: number | undefined) => Math.max(0, Number.isFinite(v) ? (v as number) : 0);

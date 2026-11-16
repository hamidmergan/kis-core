"use client";

// Simple line icons drawn in the current colour.
const PATH = {
  check: "M5 12.5l4.5 4.5L19 7.5",
  cross: "M6 6l12 12M18 6L6 18",
  right: "M4 12h16M13 5l7 7-7 7",
  down: "M12 4v16M5 13l7 7 7-7",
};

export function Ic({ d }: { d: keyof typeof PATH }) {
  return <svg className="v-cp-ic" viewBox="0 0 24 24" aria-hidden="true"><path d={PATH[d]} /></svg>;
}

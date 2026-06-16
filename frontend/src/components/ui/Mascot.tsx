"use client";

import Hilde from "./Hilde";
import Francis from "./Francis";

export type MascotState = "idle" | "thinking" | "found" | "confused" | "wave";
export type MascotVariant = "hilde" | "francis";

export interface MascotProps {
  variant: MascotVariant;
  size?: number;
  state?: MascotState;
  className?: string;
}

/** Renders the user-chosen mascot character. */
export default function Mascot({ variant, ...rest }: MascotProps) {
  return variant === "hilde" ? <Hilde {...rest} /> : <Francis {...rest} />;
}

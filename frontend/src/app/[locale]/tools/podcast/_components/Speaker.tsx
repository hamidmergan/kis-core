"use client";

import { speakerColor } from "../_colors";
import type { Person } from "../_types";

/** Initial in a coloured dot plus name and role, the same on every page that lists lines. */
export default function Speaker({ person, role, index }: { person: Person; role: string; index: number }) {
  const farbe = speakerColor(index);
  return (
    <span className="flex items-center gap-2 min-w-0">
      <span
        className="w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold shrink-0"
        style={{ backgroundColor: farbe.fg, color: "var(--background)" }}
      >
        {person.name.trim().charAt(0).toUpperCase() || "?"}
      </span>
      <span className="text-sm font-semibold truncate" style={{ color: farbe.fg }}>{person.name}</span>
      <span className="text-xs text-muted-soft truncate">{role}</span>
    </span>
  );
}

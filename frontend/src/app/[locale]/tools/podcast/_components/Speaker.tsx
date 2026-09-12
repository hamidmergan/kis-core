"use client";

import type { Person } from "../_types";

/** Initial in a ring plus name and role, the same on every page that lists lines. */
export default function Speaker({ person, role }: { person: Person; role: string }) {
  return (
    <span className="flex items-center gap-2 min-w-0">
      <span className="w-7 h-7 rounded-full border-2 border-border flex items-center justify-center text-xs font-bold shrink-0 text-foreground-soft">
        {person.name.trim().charAt(0).toUpperCase() || "?"}
      </span>
      <span className="text-sm font-medium text-foreground truncate">{person.name}</span>
      <span className="text-xs text-muted-soft truncate">{role}</span>
    </span>
  );
}

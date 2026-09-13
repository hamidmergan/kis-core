"use client";

/** A group of settings under a short heading, used by both limit tabs. */

import type { ReactNode } from "react";

export default function Block({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="space-y-4">
      <h2 className="text-sm font-semibold text-foreground-soft">{title}</h2>
      {children}
    </section>
  );
}

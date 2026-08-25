/**
 * Der Zustand einer Sache: ein Strich links vom Wort statt einer Pille.
 *
 * Fuer alles, was sich von allein aendert, also Auftraege, Konten, Einladungen.
 * Nicht fuer Marker wie Tutor oder Admin, die sagen dauerhaft was jemand ist
 * und bleiben ein rundes Schild.
 */

import type { ReactNode } from "react";
import type { StatusTone } from "@/lib/jobStatusDisplay";

export default function StatusMark({
  tone,
  pulse = false,
  className = "",
  children,
}: {
  tone: StatusTone;
  pulse?: boolean;
  className?: string;
  children: ReactNode;
}) {
  return (
    <span className={`status-mark status-mark--${tone}${pulse ? " status-mark--pulse" : ""} ${className}`}>
      {children}
    </span>
  );
}

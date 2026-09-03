"use client";

import { createContext, useContext, type ReactNode } from "react";

/** true while someone only previews the owner layout without owning anything. */
const OwnerPreviewContext = createContext(false);

export function OwnerPreviewProvider({ value, children }: { value: boolean; children: ReactNode }) {
  return <OwnerPreviewContext.Provider value={value}>{children}</OwnerPreviewContext.Provider>;
}

interface OwnerOnlyProps {
  /** Owner elements shown at all, real ownership or owner preview. */
  show: boolean;
  children: ReactNode;
}

/**
 * Single gate for everything only owners and tutors see.
 *
 * The wrapper carries `display: contents`, so it adds no box of its own and
 * cannot break a flex or grid parent. In preview mode `inert` switches off
 * clicks and focus for the whole subtree, the dashed marking sits on the
 * children (see globals.css), because the wrapper itself has no box.
 */
export function OwnerOnly({ show, children }: OwnerOnlyProps) {
  const preview = useContext(OwnerPreviewContext);
  if (!show) return null;
  if (!preview) return <>{children}</>;
  return (
    <span className="owner-preview" inert>
      {children}
    </span>
  );
}

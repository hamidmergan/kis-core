import type { Metadata } from "next";
import type { ReactNode } from "react";
import MockupRibbon from "./_components/MockupRibbon";

export const metadata: Metadata = { robots: { index: false, follow: false } };

export default function MockupLayout({ children }: { children: ReactNode }) {
  return (
    <>
      <MockupRibbon />
      {children}
    </>
  );
}

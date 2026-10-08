import type { Metadata } from "next";

// A shared link is for the people it is given to, search engines leave it out.
export const metadata: Metadata = { robots: { index: false, follow: false, nocache: true } };

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}

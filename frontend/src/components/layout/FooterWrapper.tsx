"use client";

import { usePathname } from "@/i18n/navigation";
import Footer from "./Footer";

const NO_FOOTER_PREFIXES = ["/workspace/"];

export default function FooterWrapper({ hasSession }: { hasSession: boolean }) {
  const pathname = usePathname();
  if (!hasSession) return null;
  if (NO_FOOTER_PREFIXES.some((prefix) => pathname.startsWith(prefix))) return null;
  return <Footer loggedIn />;
}

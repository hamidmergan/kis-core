"use client";

import { usePathname } from "@/i18n/navigation";
import Footer from "./Footer";

const GUEST_PATHS = ["/login", "/pending"];
const NO_FOOTER_PREFIXES = ["/workspace/"];

export default function FooterWrapper() {
  const pathname = usePathname();
  if (NO_FOOTER_PREFIXES.some((prefix) => pathname.startsWith(prefix))) return null;
  const loggedIn = !GUEST_PATHS.includes(pathname);
  return <Footer loggedIn={loggedIn} />;
}

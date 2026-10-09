"use client";

import { usePathname } from "@/i18n/navigation";
import Footer from "./Footer";

const NO_FOOTER_PATHS = ["/pending", "/campusmap"];
const NO_FOOTER_PREFIXES = ["/workspace/", "/tools/info", "/tools/pages/", "/p/", "/u/"];

export default function FooterWrapper({ hasSession }: { hasSession: boolean }) {
  const pathname = usePathname();
  if (NO_FOOTER_PREFIXES.some((prefix) => pathname.startsWith(prefix))) return null;
  if (NO_FOOTER_PATHS.includes(pathname)) return null;
  // Nobody is logged in on the login page, imprint and privacy still appear.
  return <Footer loggedIn={hasSession && pathname !== "/login"} />;
}

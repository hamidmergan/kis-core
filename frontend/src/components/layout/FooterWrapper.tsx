"use client";

import { usePathname } from "@/i18n/navigation";
import Footer from "./Footer";

const NO_FOOTER_PATHS = ["/pending"];
const NO_FOOTER_PREFIXES = ["/workspace/"];

export default function FooterWrapper({ hasSession }: { hasSession: boolean }) {
  const pathname = usePathname();
  if (NO_FOOTER_PREFIXES.some((prefix) => pathname.startsWith(prefix))) return null;
  if (NO_FOOTER_PATHS.includes(pathname)) return null;
  // Auf der Anmeldeseite ist niemand angemeldet. Ohne LDAP meldet der Server
  // trotzdem eine Sitzung, sonst stuenden KI-Hinweis und Feedback-Adresse schon
  // vor der Anmeldung da. Impressum und Datenschutz zeigt die Fusszeile immer.
  return <Footer loggedIn={hasSession && pathname !== "/login"} />;
}

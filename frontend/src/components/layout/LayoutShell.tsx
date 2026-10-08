"use client";

import { usePathname } from "@/i18n/navigation";
import HomeNotice from "@/app/[locale]/workspace/_components/HomeNotice";
import Header from "./Header";
import ImpersonationBanner from "./ImpersonationBanner";

// The access-code pages bring their own header, like the login page.
const NO_HEADER_PATHS = new Set(["/login", "/maintenance", "/pending", "/redeem", "/redeem/expired", "/evaluation", "/campusmap"]);
// An invitation carries its token in the path, so it is matched by prefix.
const NO_HEADER_PREFIXES = ["/workspace/", "/invite/", "/tools/info"];
// A page of Pages read inside a workspace is a page like any other, so it keeps the header.
const WORKSPACE_PAGE = /^\/workspace\/[^/]+\/page\//;

function matchesPrefix(pathname: string, prefixes: string[]): boolean {
  return prefixes.some((p) => pathname.startsWith(p));
}

export default function LayoutShell({
  children,
  hasSession,
}: {
  children: React.ReactNode;
  hasSession: boolean;
}) {
  const pathname = usePathname();

  const showHeader = !NO_HEADER_PATHS.has(pathname)
    && (!matchesPrefix(pathname, NO_HEADER_PREFIXES) || WORKSPACE_PAGE.test(pathname));
  // The notice bar belongs to the two landing pages, the tiles and the module list.
  const showNotice = pathname === "/services" || pathname === "/workspace";

  // The banner sits above every early return, a borrowed account must never hide it.
  return (
    <>
      <ImpersonationBanner />
      {showNotice && <HomeNotice />}
      {showHeader && <Header hasSession={hasSession} showLogout />}
      {children}
    </>
  );
}

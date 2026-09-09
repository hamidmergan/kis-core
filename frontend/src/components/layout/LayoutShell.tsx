"use client";

import { usePathname } from "@/i18n/navigation";
import HomeNotice from "@/app/[locale]/workspace/_components/HomeNotice";
import Header from "./Header";
import ImpersonationBanner from "./ImpersonationBanner";
import ToolsSidebar from "./ToolsSidebar";

// The access-code pages bring their own header, like the login page.
const NO_HEADER_PATHS = new Set(["/login", "/maintenance", "/pending", "/redeem", "/redeem/expired", "/evaluation"]);
// An invitation carries its token in the path, so it is matched by prefix.
const NO_HEADER_PREFIXES = ["/workspace/", "/invite/"];

const NO_SIDEBAR_PATHS = new Set([
  "/login",
  "/imprint",
  "/privacy",
  "/pending",
  "/maintenance",
  "/redeem",
  "/redeem/expired",
  "/evaluation",
]);
const NO_SIDEBAR_PREFIXES = ["/workspace/", "/admin", "/invite/", "/manual"];

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

  const showHeader = !NO_HEADER_PATHS.has(pathname) && !matchesPrefix(pathname, NO_HEADER_PREFIXES);
  const showSidebar =
    hasSession && !NO_SIDEBAR_PATHS.has(pathname) && !matchesPrefix(pathname, NO_SIDEBAR_PREFIXES);
  // The notice bar belongs to the start page only.
  const showNotice = pathname === "/";

  // The banner sits above every early return, a borrowed account must never hide it.
  if (!showHeader && !showSidebar)
    return (
      <>
        <ImpersonationBanner />
        {children}
      </>
    );

  if (!showSidebar) {
    return (
      <>
        <ImpersonationBanner />
        {showNotice && <HomeNotice />}
        {showHeader && <Header hasSession={hasSession} showLogout showToolsToggle={false} />}
        {children}
      </>
    );
  }

  return (
    <>
      <ImpersonationBanner />
      {showNotice && <HomeNotice />}
      {showHeader && <Header hasSession={hasSession} showLogout showToolsToggle />}
      <div className="flex items-stretch min-h-[calc(100vh-4rem)] overflow-x-hidden">
        <ToolsSidebar />
        <div className="flex-1 min-w-0">{children}</div>
      </div>
    </>
  );
}

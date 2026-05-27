"use client";

import { usePathname } from "@/i18n/navigation";
import Header from "./Header";
import ToolsSidebar from "./ToolsSidebar";

const NO_HEADER_PATHS = new Set(["/login", "/wartung", "/pending"]);
const NO_HEADER_PREFIXES = ["/workspace/"];

const NO_SIDEBAR_PATHS = new Set([
  "/login",
  "/imprint",
  "/privacy",
  "/pending",
  "/wartung",
]);
const NO_SIDEBAR_PREFIXES = ["/workspace/", "/admin"];

function matchesPrefix(pathname: string, prefixes: string[]): boolean {
  return prefixes.some((p) => pathname.startsWith(p));
}

export default function LayoutShell({
  children,
  hasSession,
  localMode = false,
}: {
  children: React.ReactNode;
  hasSession: boolean;
  localMode?: boolean;
}) {
  const pathname = usePathname();

  const showHeader = !NO_HEADER_PATHS.has(pathname) && !matchesPrefix(pathname, NO_HEADER_PREFIXES);
  const showSidebar =
    hasSession && !NO_SIDEBAR_PATHS.has(pathname) && !matchesPrefix(pathname, NO_SIDEBAR_PREFIXES);

  if (!showHeader && !showSidebar) return <>{children}</>;

  if (!showSidebar) {
    return (
      <>
        {showHeader && <Header hasSession={hasSession} showLogout={!localMode} showToolsToggle={false} />}
        {children}
      </>
    );
  }

  return (
    <>
      {showHeader && <Header hasSession={hasSession} showLogout={!localMode} showToolsToggle />}
      <div className="flex items-stretch min-h-[calc(100vh-4rem)] overflow-x-hidden">
        <ToolsSidebar />
        <div className="flex-1 min-w-0">{children}</div>
      </div>
    </>
  );
}

"use client";

import { usePathname } from "next/navigation";
import Header from "./Header";
import ToolsSidebar from "./ToolsSidebar";

const NO_HEADER_PATHS = new Set(["/", "/login", "/wartung", "/pending", "/embedpdf-test"]);
const NO_HEADER_PREFIXES = ["/workspaces/"];

const NO_SIDEBAR_PATHS = new Set([
  "/",
  "/login",
  "/imprint",
  "/privacy",
  "/pending",
  "/wartung",
  "/embedpdf-test",
]);
const NO_SIDEBAR_PREFIXES = ["/workspaces/"];

function matchesPrefix(pathname: string, prefixes: string[]): boolean {
  return prefixes.some((p) => pathname.startsWith(p));
}

export default function LayoutShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  const showHeader = !NO_HEADER_PATHS.has(pathname) && !matchesPrefix(pathname, NO_HEADER_PREFIXES);
  const showSidebar = !NO_SIDEBAR_PATHS.has(pathname) && !matchesPrefix(pathname, NO_SIDEBAR_PREFIXES);

  if (!showHeader && !showSidebar) return <>{children}</>;

  if (!showSidebar) {
    return (
      <>
        {showHeader && <Header showLogout showToolsToggle={false} />}
        {children}
      </>
    );
  }

  return (
    <>
      {showHeader && <Header showLogout showToolsToggle />}
      <div className="flex items-stretch min-h-[calc(100vh-4rem)] overflow-x-hidden">
        <ToolsSidebar />
        <div className="flex-1 min-w-0">{children}</div>
      </div>
    </>
  );
}

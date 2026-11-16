import { hasModule, toolKeyFromPath } from "@/lib/modules";
import { EMPTY_PERMS, PERM, hasPerm } from "@/lib/permissions";
import type { AuthStatus } from "@/types";

/** Shared pages and collections are the only paths a login leads back to. */
export function isReturnPath(path: string | null | undefined): path is string {
  return !!path && /^\/(p|u)\/[A-Za-z0-9]{6,32}$/.test(path);
}

/** Where a protected page sends this account instead, null when it may stay. */
export function redirectFor(status: AuthStatus, pathname: string | null): string | null {
  if (!status.authenticated) {
    // An expired access says so on the login page instead of landing there mute.
    if (status.reason === "access_expired") return "/login?expired=1";
    // A shared page is opened from a link, after the login the person lands on it again.
    return isReturnPath(pathname) ? `/login?next=${encodeURIComponent(pathname)}` : "/login";
  }
  const perms = status.permissions ?? EMPTY_PERMS;
  const hasAiaModule = hasModule(status.modules, "aia");

  // The calendar is pure assistant.
  if ((pathname === "/calendar" || pathname?.startsWith("/calendar/")) && !hasAiaModule) return "/services";
  if (pathname?.startsWith("/admin") && !perms.allow_admin_panel) return "/workspace";
  if (pathname?.startsWith("/manual") && !hasPerm(perms, PERM.manual)) return "/workspace";
  if (pathname?.startsWith("/tools/")) {
    const key = toolKeyFromPath(pathname);
    if (key && !perms.tools.includes(key)) return "/workspace";
  }
  // Jobs only come from tools, without a tool permission there is nothing to see.
  if (pathname?.startsWith("/my-jobs") && perms.tools.length === 0) return "/workspace";
  // The list at /workspace and every module below it belong to the assistant, whoever cannot use it falls back to the services.
  if ((pathname === "/workspace" || pathname?.startsWith("/workspace/")) && (!perms.allow_aia || !hasAiaModule)) return "/services";
  return null;
}

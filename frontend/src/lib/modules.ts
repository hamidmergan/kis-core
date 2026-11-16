import type { UserPermissions } from "@/types";

const ALL_MODULES = ["aia", "tools"] as const;

/** Order of the tools on the start page, by importance for teaching. */
const TOOL_ROUTES = [
  { key: "campus", href: "/tools/info" },
  { key: "translation", href: "/tools/translate" },
  { key: "tts", href: "/tools/tts" },
  { key: "transcription", href: "/tools/stt" },
  { key: "image", href: "/tools/image" },
  { key: "summary", href: "/tools/summarize" },
  { key: "pages", href: "/tools/pages" },
  { key: "podcast", href: "/tools/podcast" },
  { key: "praesentation", href: "/tools/praesentation" },
  { key: "screencast", href: "/tools/screencast" },
  { key: "interpreter", href: "/tools/interpreter" },
  { key: "glossary", href: "/tools/glossary" },
] as const;

export type ToolKey = (typeof TOOL_ROUTES)[number]["key"];

/** Whether this installation has the module, a missing list means an older server with all of them. */
export function hasModule(modules: readonly string[] | undefined, module: (typeof ALL_MODULES)[number]): boolean {
  return (modules ?? ALL_MODULES).includes(module);
}

/** The tool behind a path like /tools/stt/..., null for anything else. */
export function toolKeyFromPath(pathname: string | null): ToolKey | null {
  if (!pathname) return null;
  const segs = pathname.split("/").filter(Boolean);
  const idx = segs.indexOf("tools");
  if (idx === -1 || !segs[idx + 1]) return null;
  return TOOL_ROUTES.find((t) => t.href === `/tools/${segs[idx + 1]}`)?.key ?? null;
}

export type HomeTarget =
  | { kind: "aia"; href: "/workspace" }
  | { kind: "tool"; key: ToolKey; href: string };

/** Everything the start page may offer, the assistant first. One target means a straight redirect, more means tiles. */
export function homeTargets(
  modules: readonly string[] | undefined,
  permissions: UserPermissions,
  enabledKeys?: readonly string[],
): HomeTarget[] {
  const ziele: HomeTarget[] = [];
  if (hasModule(modules, "aia") && permissions.allow_aia) ziele.push({ kind: "aia", href: "/workspace" });
  if (hasModule(modules, "tools")) {
    const frei = (key: string) => enabledKeys === undefined || enabledKeys.includes(key);
    for (const key of sichtbareWerkzeuge(permissions, frei)) {
      ziele.push({ kind: "tool", key, href: TOOL_ROUTES.find((t) => t.key === key)!.href });
    }
  }
  return ziele;
}

/** Without a reliable answer every tool counts as released. */
export function enabledToolKeys(
  tools: { key: string; enabled: boolean }[] | null,
): string[] | undefined {
  if (!tools || tools.length === 0) return undefined;
  return tools.filter((t) => t.enabled).map((t) => t.key);
}

/** The tools somebody actually sees, in the order of the start page. */
export function sichtbareWerkzeuge(
  permissions: UserPermissions,
  isToolEnabled: (key: string) => boolean,
): ToolKey[] {
  return TOOL_ROUTES.filter((t) => isToolEnabled(t.key) && permissions.tools.includes(t.key)).map(
    (t) => t.key,
  );
}

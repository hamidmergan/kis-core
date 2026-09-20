import type { UserPermissions } from "@/types";

export const ALL_MODULES = ["aia", "tools"] as const;

/** Order of the tools on the start page, nach Wichtigkeit für die Lehre. */
export const TOOL_ROUTES = [
  { key: "translation", href: "/tools/translate" },
  { key: "tts", href: "/tools/tts" },
  { key: "transcription", href: "/tools/stt" },
  { key: "summary", href: "/tools/summarize" },
  { key: "screencast", href: "/tools/screencast" },
  { key: "podcast", href: "/tools/podcast" },
  { key: "praesentation", href: "/tools/praesentation" },
  { key: "image", href: "/tools/image" },
  { key: "interpreter", href: "/tools/interpreter" },
  { key: "glossary", href: "/tools/glossary" },
] as const;

export type ToolKey = (typeof TOOL_ROUTES)[number]["key"];

/** Who a start page group addresses: teaching staff, students, or both. */
export type Audience = "lehrende" | "studierende";

/** The tools group addresses teaching staff only for now. */
export const TOOLS_AUDIENCE: readonly Audience[] = ["lehrende"];

/** The assistant is the only group reaching teaching staff and students alike. */
export const AIA_AUDIENCE: readonly Audience[] = ["lehrende", "studierende"];

export type HomeTarget =
  | { kind: "aia"; href: "/workspace" }
  | { kind: "tool"; key: ToolKey; href: string };

/** Everything the start page may offer, the assistant first. One target means a straight redirect, more means tiles. */
export function homeTargets(
  modules: readonly string[] | undefined,
  permissions: UserPermissions,
  enabledKeys?: readonly string[],
): HomeTarget[] {
  const aktiv = modules ?? ALL_MODULES;
  const ziele: HomeTarget[] = [];
  if (aktiv.includes("aia") && permissions.allow_aia) ziele.push({ kind: "aia", href: "/workspace" });
  if (aktiv.includes("tools")) {
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

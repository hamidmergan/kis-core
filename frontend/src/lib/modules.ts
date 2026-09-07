import type { UserPermissions } from "@/types";

export const ALL_MODULES = ["aia", "tools"] as const;

/** Reihenfolge der Werkzeuge, geteilt mit der Seitenleiste. */
export const TOOL_ROUTES = [
  { key: "translation", href: "/tools/translate" },
  { key: "tts", href: "/tools/tts" },
  { key: "transcription", href: "/tools/stt" },
  { key: "image", href: "/tools/image" },
  { key: "summary", href: "/tools/summarize" },
  { key: "screencast", href: "/tools/screencast" },
  { key: "glossary", href: "/tools/glossary" },
] as const;

export type ToolKey = (typeof TOOL_ROUTES)[number]["key"];

export type HomeTarget =
  | { kind: "aia" }
  | { kind: "tool"; href: string }
  | { kind: "locked" };

/** Wohin die Startseite fuehrt, abhaengig vom Profil, den Rechten und den global freigegebenen Werkzeugen. */
export function pickHomeTarget(
  modules: readonly string[] | undefined,
  permissions: UserPermissions,
  enabledKeys?: readonly string[],
): HomeTarget {
  const aktiv = modules ?? ALL_MODULES;
  if (aktiv.includes("aia") && permissions.allow_aia) return { kind: "aia" };
  if (aktiv.includes("tools")) {
    const ersteres = TOOL_ROUTES.find(
      (t) => permissions.tools.includes(t.key) && (enabledKeys === undefined || enabledKeys.includes(t.key)),
    );
    if (ersteres) return { kind: "tool", href: ersteres.href };
  }
  return { kind: "locked" };
}

/** Ohne belastbare Antwort gilt jedes Werkzeug als frei, genau wie in der Seitenleiste. */
export function enabledToolKeys(
  tools: { key: string; enabled: boolean }[] | null,
): string[] | undefined {
  if (!tools || tools.length === 0) return undefined;
  return tools.filter((t) => t.enabled).map((t) => t.key);
}

/** The tools somebody actually sees, in the order of the sidebar, so list and tour never disagree. */
export function sichtbareWerkzeuge(
  permissions: UserPermissions,
  isToolEnabled: (key: string) => boolean,
): ToolKey[] {
  return TOOL_ROUTES.filter((t) => isToolEnabled(t.key) && permissions.tools.includes(t.key)).map(
    (t) => t.key,
  );
}

import type { UserPermissions } from "@/types";

export const ALL_MODULES = ["aia", "tools"] as const;

/** Reihenfolge der Werkzeuge, geteilt mit der Seitenleiste. */
export const TOOL_ROUTES: { key: string; href: string }[] = [
  { key: "translation", href: "/tools/translate" },
  { key: "tts", href: "/tools/tts" },
  { key: "transcription", href: "/tools/stt" },
  { key: "image", href: "/tools/image" },
  { key: "summary", href: "/tools/summarize" },
  { key: "screencast", href: "/tools/screencast" },
  { key: "glossary", href: "/tools/glossary" },
];

export type HomeTarget =
  | { kind: "aia" }
  | { kind: "tool"; href: string }
  | { kind: "locked" };

/** Wohin die Startseite fuehrt, abhaengig vom Profil und den Rechten. */
export function pickHomeTarget(
  modules: readonly string[] | undefined,
  permissions: UserPermissions,
): HomeTarget {
  const aktiv = modules ?? ALL_MODULES;
  if (aktiv.includes("aia") && permissions.allow_aia) return { kind: "aia" };
  if (aktiv.includes("tools")) {
    const ersteres = TOOL_ROUTES.find((t) => permissions.tools.includes(t.key));
    if (ersteres) return { kind: "tool", href: ersteres.href };
  }
  return { kind: "locked" };
}

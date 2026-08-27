import type { UserPermissions } from "@/types";

/**
 * Die Rechte-Schluessel, die der Adminbereich kennt.
 *
 * Spiegelbild von `backend/src/permissions_registry.py`. Der Server bleibt die
 * Wahrheit, er prueft jede Anfrage. Diese Liste sagt der Oberflaeche nur, welche
 * Seite an welchem Recht haengt, damit die Seitenleiste nichts anzeigt, was
 * hinterher ein 403 waere.
 *
 * Die Texte dazu stehen in `messages/{de,en}.json` unter `admin.permissions`.
 */
export const PERM = {
  aiaUse: "aia.use",
  aiaWorkspaceCreate: "aia.workspace.create",

  toolsRelease: "settings.werkzeuge.release",
  toolsJobs: "settings.werkzeuge.jobs",
  toolsStats: "settings.werkzeuge.stats",
  toolsLimits: "settings.werkzeuge.limits",
  aiaSources: "settings.assistent.sources",
  aiaLevel: "settings.assistent.level",
  aiaUsage: "settings.assistent.usage",
  providers: "settings.anbieter",
  usersPending: "settings.nutzer.pending",
  usersWhitelist: "settings.nutzer.whitelist",
  usersAll: "settings.nutzer.users",
  usersRoles: "settings.nutzer.roles",
  system: "settings.system",
  mascot: "settings.mascot",
  // Der Bereich Statistik hat fuenf Reiter. Zwei sind umgezogen und behalten
  // ihren alten Schluessel (toolsStats, aiaUsage), damit bestehende Rollen
  // nichts verlieren. Die anderen drei haben eigene.
  statsUsers: "settings.statistik.nutzer",
  statsModels: "settings.statistik.modelle",
  // Der einzige Schluessel der Gruppe, der nicht die ganze Plattform aufmacht:
  // er zeigt nur Module, die dem Anrufer gehoeren oder die er betreut.
  statsOwn: "settings.statistik.eigene",
  // Kein Recht, etwas einzustellen, sondern weitermachen zu duerfen, waehrend
  // die Plattform fuer alle anderen zu ist.
  maintenanceAccess: "settings.wartung.zugang",
} as const;

export type PermissionKey = (typeof PERM)[keyof typeof PERM] | string;

/** Die Gruppe Einstellungen, also alles was eine Seite des Bereichs aufschliesst. */
export const SETTINGS_PERMS: string[] = [
  PERM.toolsRelease,
  PERM.toolsJobs,
  PERM.toolsStats,
  PERM.toolsLimits,
  PERM.aiaSources,
  PERM.aiaLevel,
  PERM.aiaUsage,
  PERM.providers,
  PERM.usersPending,
  PERM.usersWhitelist,
  PERM.usersAll,
  PERM.usersRoles,
  PERM.system,
  PERM.mascot,
  PERM.statsUsers,
  PERM.statsModels,
  PERM.statsOwn,
  PERM.maintenanceAccess,
];

export const EMPTY_PERMS: UserPermissions = {
  allow_admin_panel: false,
  allow_aia: false,
  allow_workspace_create: false,
  tools: [],
  keys: [],
  allow_ldap_user_create: false,
};

/** Ob die Rechte einen der genannten Schluessel enthalten. */
export function hasPerm(perms: UserPermissions | undefined, ...keys: string[]): boolean {
  if (!perms?.keys) return false;
  return keys.some((k) => perms.keys.includes(k));
}

/**
 * Traegt jemand jedes Einstellungsrecht, ist er faktisch Administrator, egal
 * unter welchem Rollennamen. Das entscheidet, ob der Bereich "Administration"
 * oder "Einstellungen" heisst.
 *
 * Gemessen an den Rechten und nicht am Rollennamen: eine eigene Rolle mit allen
 * Haekchen soll nicht "Einstellungen" heissen, waehrend sie alles darf.
 */
export function isFullAdmin(perms: UserPermissions | undefined): boolean {
  if (!perms?.keys) return false;
  return SETTINGS_PERMS.every((k) => perms.keys.includes(k));
}

/** Schluessel unter `header` fuer den Namen des Bereichs. */
export function areaLabelKey(perms: UserPermissions | undefined): "admin" | "settings" {
  return isFullAdmin(perms) ? "admin" : "settings";
}

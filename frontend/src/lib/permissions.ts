import type { UserPermissions } from "@/types";

/** Mirror of the server's permission keys so the sidebar offers no 403. */
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
  // Sich als jemand anderes anmelden, um ein gemeldetes Problem selbst zu sehen.
  usersImpersonate: "settings.nutzer.impersonate",
  system: "settings.system",
  mascot: "settings.mascot",
  // Two tabs keep their old key so existing roles lose nothing.
  statsUsers: "settings.statistik.nutzer",
  statsModels: "settings.statistik.modelle",
  // The only key of the group that shows just your own and tutored modules.
  statsOwn: "settings.statistik.eigene",
  // Not a settings right but the right to keep working while everything is shut.
  maintenanceAccess: "settings.wartung.zugang",
} as const;

/** The settings group, everything that unlocks a page of the area. */
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
  PERM.usersImpersonate,
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

/** Whether the permissions contain one of the named keys. */
export function hasPerm(perms: UserPermissions | undefined, ...keys: string[]): boolean {
  if (!perms?.keys) return false;
  return keys.some((k) => perms.keys.includes(k));
}

/** Whoever holds every settings permission is effectively an administrator, measured by the permissions. */
export function isFullAdmin(perms: UserPermissions | undefined): boolean {
  if (!perms?.keys) return false;
  return SETTINGS_PERMS.every((k) => perms.keys.includes(k));
}

/** Key under `header` for the name of the area. */
export function areaLabelKey(perms: UserPermissions | undefined): "admin" | "settings" {
  return isFullAdmin(perms) ? "admin" : "settings";
}

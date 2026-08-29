/** Who is offered the button that logs you in as them. */

import { PERM } from "@/lib/permissions";

type Zeile = {
  id: number;
  email?: string | null;
  role?: string;
  custom_role_id?: number | null;
  active?: number;
};

type Kontext = {
  userId: number;
  adminEmail: string;
  /** Custom roles that may hand out rights, they stay closed. */
  gesperrteRollen: number[];
};

/** The keys that let an account change who may do what. */
export const RECHTE_VERWALTUNG: string[] = [
  PERM.usersPending,
  PERM.usersWhitelist,
  PERM.usersAll,
  PERM.usersRoles,
  PERM.usersImpersonate,
];

/** Ids of the custom roles that must stay closed. */
export function gesperrteRollenIds(
  rollen: { id: number; permissions?: string[] }[],
): number[] {
  return rollen
    .filter((r) => (r.permissions ?? []).some((k) => RECHTE_VERWALTUNG.includes(k)))
    .map((r) => r.id);
}

/** Mirrors the server gate so no button leads into a 403. */
export function canImpersonate(zeile: Zeile, ich: Kontext): boolean {
  if (zeile.id === ich.userId) return false;
  if (zeile.active === 0) return false;
  const mail = (zeile.email || "").toLowerCase();
  if (mail && ich.adminEmail && mail === ich.adminEmail.toLowerCase()) return false;
  if (zeile.role === "admin") return false;
  if (zeile.role === "custom" && zeile.custom_role_id != null) {
    return !ich.gesperrteRollen.includes(zeile.custom_role_id);
  }
  return true;
}

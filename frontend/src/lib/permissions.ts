import type { UserPermissions } from "@/types";

export const EMPTY_PERMS: UserPermissions = {
  allow_admin_panel: false,
  allow_aia: false,
  allow_workspace_create: false,
  tools: [],
};

export function hasToolAccess(perms: UserPermissions | undefined, toolKey: string): boolean {
  return !!perms?.tools?.includes(toolKey);
}

export function canUseAia(perms: UserPermissions | undefined): boolean {
  return !!perms?.allow_aia;
}

export function canCreateWorkspace(perms: UserPermissions | undefined): boolean {
  return !!perms?.allow_workspace_create;
}

export function isAdmin(perms: UserPermissions | undefined): boolean {
  return !!perms?.allow_admin_panel;
}

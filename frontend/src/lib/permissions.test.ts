import { describe, expect, it } from "vitest";

import { EMPTY_PERMS, PERM, SETTINGS_PERMS, areaLabelKey, hasPerm, isFullAdmin } from "./permissions";
import type { UserPermissions } from "@/types";

function perms(keys: string[]): UserPermissions {
  return { ...EMPTY_PERMS, keys, allow_admin_panel: keys.some((k) => k.startsWith("settings.")) };
}

describe("hasPerm", () => {
  it("findet einen von mehreren Schluesseln", () => {
    expect(hasPerm(perms([PERM.aiaLevel]), PERM.system, PERM.aiaLevel)).toBe(true);
  });

  it("sagt nein, wenn keiner passt", () => {
    expect(hasPerm(perms([PERM.aiaLevel]), PERM.system)).toBe(false);
  });

  it("haelt fehlende Rechte aus, statt zu werfen", () => {
    expect(hasPerm(undefined, PERM.system)).toBe(false);
  });
});

describe("isFullAdmin", () => {
  it("nur wer jedes Einstellungsrecht hat, ist Administrator", () => {
    expect(isFullAdmin(perms(SETTINGS_PERMS))).toBe(true);
  });

  it("ein fehlendes Recht reicht, um es nicht zu sein", () => {
    expect(isFullAdmin(perms(SETTINGS_PERMS.filter((k) => k !== PERM.system)))).toBe(false);
  });

  // Der Anlass des Umbaus: der Sprachexperte darf in den Bereich, heisst dort
  // aber "Einstellungen" und nicht "Administration".
  it("der Sprachexperte ist kein Administrator", () => {
    const sprachexperte = perms([PERM.aiaUse, PERM.aiaLevel]);
    expect(sprachexperte.allow_admin_panel).toBe(true);
    expect(isFullAdmin(sprachexperte)).toBe(false);
    expect(areaLabelKey(sprachexperte)).toBe("settings");
  });

  it("der Administrator behaelt sein Wort", () => {
    expect(areaLabelKey(perms(SETTINGS_PERMS))).toBe("admin");
  });
});

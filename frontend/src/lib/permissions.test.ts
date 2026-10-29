import { describe, expect, it } from "vitest";

import { EMPTY_PERMS, PERM, SETTINGS_PERMS, STATS_PERMS, areaLabelKey, hasPerm, isFullAdmin } from "./permissions";
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

  // The language expert may enter, but the area is called settings there.
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

// Teachers read their modules' numbers on the module itself, not in the settings.
describe("Statistik einer Lehrperson", () => {
  it("kennt gar kein Recht mehr fuer eigene Module", () => {
    expect(Object.values(PERM)).not.toContain("settings.statistik.eigene");
  });

  it("oeffnet mit dem blossen Zugang zum Assistenten keinen Bereich", () => {
    expect(perms([PERM.aiaUse]).allow_admin_panel).toBe(false);
  });

  it("macht aus einer Lehrperson keinen Administrator", () => {
    expect(isFullAdmin(perms([PERM.aiaUse]))).toBe(false);
  });
});

// The link says what is behind it, statistics alone is not an administration.
describe("areaLabelKey", () => {
  it("nennt den Bereich Statistik, wenn nur Statistik-Rechte da sind", () => {
    expect(areaLabelKey(perms([PERM.aiaUse, PERM.statsUsers]))).toBe("stats");
    expect(areaLabelKey(perms(STATS_PERMS))).toBe("stats");
  });

  it("nennt ihn Verwaltung, sobald ein anderes Recht dazukommt", () => {
    expect(areaLabelKey(perms([PERM.statsUsers, PERM.aiaLevel]))).toBe("settings");
  });

  it("zaehlt den Wartungszugang nicht als Verwaltung", () => {
    expect(areaLabelKey(perms([PERM.statsUsers, PERM.maintenanceAccess]))).toBe("stats");
  });

  it("laesst niemanden ohne Recht als Statistik durchgehen", () => {
    expect(areaLabelKey(perms([PERM.aiaUse]))).toBe("settings");
    expect(areaLabelKey(undefined)).toBe("settings");
  });
});

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

// The fifth statistics tab is the only one that does not open the whole platform.
describe("Statistik nur fuer eigene Module", () => {
  it("kennt den Schluessel aus dem Katalog des Servers", () => {
    expect(PERM.statsOwn).toBe("settings.statistik.eigene");
  });

  it("zaehlt zu den Einstellungsrechten und oeffnet damit den Bereich", () => {
    expect(SETTINGS_PERMS).toContain(PERM.statsOwn);
    expect(perms([PERM.statsOwn]).allow_admin_panel).toBe(true);
  });

  it("macht aus einer Lehrperson keinen Administrator", () => {
    const dozentin = perms([PERM.aiaUse, PERM.statsOwn]);
    expect(isFullAdmin(dozentin)).toBe(false);
  });

  it("schliesst die globale Statistik nicht mit auf", () => {
    expect(hasPerm(perms([PERM.statsOwn]), PERM.aiaUsage, PERM.statsUsers)).toBe(false);
  });
});

// The link says what is behind it, statistics alone is not an administration.
describe("areaLabelKey", () => {
  it("nennt den Bereich Statistik, wenn nur Statistik-Rechte da sind", () => {
    expect(areaLabelKey(perms([PERM.aiaUse, PERM.statsOwn]))).toBe("stats");
    expect(areaLabelKey(perms(STATS_PERMS))).toBe("stats");
  });

  it("nennt ihn Verwaltung, sobald ein anderes Recht dazukommt", () => {
    expect(areaLabelKey(perms([PERM.statsOwn, PERM.aiaLevel]))).toBe("settings");
  });

  it("zaehlt den Wartungszugang nicht als Verwaltung", () => {
    expect(areaLabelKey(perms([PERM.statsOwn, PERM.maintenanceAccess]))).toBe("stats");
  });

  it("laesst niemanden ohne Recht als Statistik durchgehen", () => {
    expect(areaLabelKey(perms([PERM.aiaUse]))).toBe("settings");
    expect(areaLabelKey(undefined)).toBe("settings");
  });
});

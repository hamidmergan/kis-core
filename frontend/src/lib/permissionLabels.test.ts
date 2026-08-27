import { describe, expect, it } from "vitest";

import de from "../../messages/de.json";
import en from "../../messages/en.json";
import { PERM, SETTINGS_PERMS } from "./permissions";

/** Every permission key needs its text, otherwise the bare key appears in the editor. */

/** `settings.statistik.eigene` -> messages.admin.permissions.settings.statistik.eigene */
function label(messages: Record<string, unknown>, key: string): unknown {
  return key
    .split(".")
    .reduce<unknown>(
      (knoten, teil) =>
        knoten && typeof knoten === "object"
          ? (knoten as Record<string, unknown>)[teil]
          : undefined,
      (messages.admin as Record<string, unknown>).permissions,
    );
}

const SPRACHEN: [string, Record<string, unknown>][] = [
  ["de", de as Record<string, unknown>],
  ["en", en as Record<string, unknown>],
];

describe.each(SPRACHEN)("Beschriftungen der Rechte (%s)", (_sprache, messages) => {
  it.each(Object.values(PERM))("%s hat einen Text", (key) => {
    expect(typeof label(messages, key)).toBe("string");
  });
});

describe("Die beiden Statistik-Rechte sind auseinanderzuhalten", () => {
  it("das globale sagt im Text, dass es alle Module meint", () => {
    // Otherwise two identically named rows appear, one of which opens everything.
    expect(label(de as Record<string, unknown>, PERM.aiaUsage)).toMatch(/alle Module/i);
  });

  it("das eingeschraenkte sagt, worauf es sich beschraenkt", () => {
    expect(label(de as Record<string, unknown>, PERM.statsOwn)).toMatch(/eigen|betreu/i);
  });

  it("beide zaehlen zu den Einstellungsrechten", () => {
    expect(SETTINGS_PERMS).toEqual(expect.arrayContaining([PERM.aiaUsage, PERM.statsOwn]));
  });
});

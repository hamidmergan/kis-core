import { describe, expect, it } from "vitest";
import { pickHomeTarget } from "./modules";
import { EMPTY_PERMS } from "./permissions";

const mitAia = { ...EMPTY_PERMS, allow_aia: true };
const mitTools = { ...EMPTY_PERMS, tools: ["tts", "translation"] };

describe("pickHomeTarget", () => {
  it("zeigt den Assistenten, wenn Modul und Recht da sind", () => {
    expect(pickHomeTarget(["aia", "tools"], mitAia)).toEqual({ kind: "aia" });
  });

  it("schickt ohne Assistenten-Modul auf das erste erlaubte Werkzeug", () => {
    expect(pickHomeTarget(["tools"], mitTools)).toEqual({
      kind: "tool",
      href: "/tools/translate",
    });
  });

  it("haelt die Reihenfolge der Werkzeugliste ein, nicht die der Rechte", () => {
    const perms = { ...EMPTY_PERMS, tools: ["screencast", "tts"] };
    expect(pickHomeTarget(["tools"], perms)).toEqual({
      kind: "tool",
      href: "/tools/tts",
    });
  });

  it("sperrt, wenn das Modul da ist aber das Recht fehlt", () => {
    expect(pickHomeTarget(["aia", "tools"], EMPTY_PERMS)).toEqual({ kind: "locked" });
  });

  it("sperrt, wenn nur Werkzeuge da sind aber kein Werkzeug erlaubt ist", () => {
    expect(pickHomeTarget(["tools"], EMPTY_PERMS)).toEqual({ kind: "locked" });
  });

  it("nimmt den Assistenten, wenn beide Module und beide Rechte da sind", () => {
    const perms = { ...EMPTY_PERMS, allow_aia: true, tools: ["tts"] };
    expect(pickHomeTarget(["aia", "tools"], perms)).toEqual({ kind: "aia" });
  });

  it("faellt ohne Angabe auf beide Module zurueck", () => {
    expect(pickHomeTarget(undefined, mitAia)).toEqual({ kind: "aia" });
  });
});

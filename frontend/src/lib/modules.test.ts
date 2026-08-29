import { describe, expect, it } from "vitest";
import { pickHomeTarget, enabledToolKeys } from "./modules";
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

  it("ueberspringt ein global abgeschaltetes Werkzeug", () => {
    const perms = { ...EMPTY_PERMS, tools: ["translation", "tts"] };
    expect(pickHomeTarget(["tools"], perms, ["tts"])).toEqual({
      kind: "tool",
      href: "/tools/tts",
    });
  });

  it("sperrt, wenn jedes erlaubte Werkzeug global abgeschaltet ist", () => {
    const perms = { ...EMPTY_PERMS, tools: ["translation"] };
    expect(pickHomeTarget(["tools"], perms, [])).toEqual({ kind: "locked" });
  });

  it("beruecksichtigt ohne Angabe der Freigaben alle erlaubten Werkzeuge", () => {
    const perms = { ...EMPTY_PERMS, tools: ["translation"] };
    expect(pickHomeTarget(["tools"], perms)).toEqual({
      kind: "tool",
      href: "/tools/translate",
    });
  });

  it("sperrt bei leerer Modulliste statt auf beide Module zu fallen", () => {
    expect(pickHomeTarget([], { ...EMPTY_PERMS, allow_aia: true })).toEqual({ kind: "locked" });
  });

  it("sperrt in einer reinen Assistenten-Anlage ohne aia-Recht", () => {
    const perms = { ...EMPTY_PERMS, tools: ["tts"] };
    expect(pickHomeTarget(["aia"], perms)).toEqual({ kind: "locked" });
  });
});

describe("enabledToolKeys", () => {
  it("gibt undefined, wenn die Liste noch nicht da ist", () => {
    expect(enabledToolKeys(null)).toBeUndefined();
  });

  it("gibt undefined bei leerer Liste, weil das nur ein gescheiterter Abruf sein kann", () => {
    expect(enabledToolKeys([])).toBeUndefined();
  });

  it("gibt die freigegebenen Schluessel", () => {
    const tools = [
      { key: "translation", enabled: true },
      { key: "tts", enabled: false },
      { key: "image", enabled: true },
    ];
    expect(enabledToolKeys(tools)).toEqual(["translation", "image"]);
  });

  it("gibt eine leere Liste, wenn eine echte Antwort alles sperrt", () => {
    const tools = [
      { key: "translation", enabled: false },
      { key: "tts", enabled: false },
    ];
    expect(enabledToolKeys(tools)).toEqual([]);
  });
});

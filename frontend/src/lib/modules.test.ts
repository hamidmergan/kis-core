import { describe, expect, it } from "vitest";
import { homeTargets, enabledToolKeys, sichtbareWerkzeuge } from "./modules";
import { EMPTY_PERMS } from "./permissions";

const mitAia = { ...EMPTY_PERMS, allow_aia: true };
const mitTools = { ...EMPTY_PERMS, tools: ["tts", "translation"] };
const AIA = { kind: "aia", href: "/workspace" };

describe("homeTargets", () => {
  it("liefert nur den Assistenten, wenn Modul und Recht da sind und kein Werkzeug", () => {
    expect(homeTargets(["aia", "tools"], mitAia)).toEqual([AIA]);
  });

  it("stellt den Assistenten vor die Werkzeuge", () => {
    const perms = { ...EMPTY_PERMS, allow_aia: true, tools: ["tts", "translation"] };
    expect(homeTargets(["aia", "tools"], perms)).toEqual([
      AIA,
      { kind: "tool", key: "translation", href: "/tools/translate" },
      { kind: "tool", key: "tts", href: "/tools/tts" },
    ]);
  });

  it("liefert ohne Assistenten-Modul nur die erlaubten Werkzeuge", () => {
    expect(homeTargets(["tools"], mitTools)).toEqual([
      { kind: "tool", key: "translation", href: "/tools/translate" },
      { kind: "tool", key: "tts", href: "/tools/tts" },
    ]);
  });

  it("haelt die Reihenfolge der Werkzeugliste ein, nicht die der Rechte", () => {
    const perms = { ...EMPTY_PERMS, tools: ["screencast", "tts"] };
    expect(homeTargets(["tools"], perms).map((z) => z.href)).toEqual(["/tools/tts", "/tools/screencast"]);
  });

  it("stellt die Dienste für die Lehre vor das Glossar", () => {
    const perms = { ...EMPTY_PERMS, tools: ["podcast", "glossary", "screencast", "praesentation"] };
    expect(homeTargets(["tools"], perms).map((z) => z.href)).toEqual([
      "/tools/podcast",
      "/tools/praesentation",
      "/tools/screencast",
      "/tools/glossary",
    ]);
  });

  it("ist leer, wenn das Modul da ist aber das Recht fehlt", () => {
    expect(homeTargets(["aia", "tools"], EMPTY_PERMS)).toEqual([]);
  });

  it("ist leer, wenn nur Werkzeuge da sind aber kein Werkzeug erlaubt ist", () => {
    expect(homeTargets(["tools"], EMPTY_PERMS)).toEqual([]);
  });

  it("faellt ohne Angabe auf beide Module zurueck", () => {
    expect(homeTargets(undefined, mitAia)).toEqual([AIA]);
  });

  it("ueberspringt ein global abgeschaltetes Werkzeug", () => {
    const perms = { ...EMPTY_PERMS, tools: ["translation", "tts"] };
    expect(homeTargets(["tools"], perms, ["tts"])).toEqual([
      { kind: "tool", key: "tts", href: "/tools/tts" },
    ]);
  });

  it("ist leer, wenn jedes erlaubte Werkzeug global abgeschaltet ist", () => {
    const perms = { ...EMPTY_PERMS, tools: ["translation"] };
    expect(homeTargets(["tools"], perms, [])).toEqual([]);
  });

  it("beruecksichtigt ohne Angabe der Freigaben alle erlaubten Werkzeuge", () => {
    const perms = { ...EMPTY_PERMS, tools: ["translation"] };
    expect(homeTargets(["tools"], perms)).toEqual([
      { kind: "tool", key: "translation", href: "/tools/translate" },
    ]);
  });

  it("ist leer bei leerer Modulliste statt auf beide Module zu fallen", () => {
    expect(homeTargets([], mitAia)).toEqual([]);
  });

  it("ignoriert Werkzeugrechte in einer reinen Assistenten-Anlage", () => {
    const perms = { ...EMPTY_PERMS, allow_aia: true, tools: ["tts"] };
    expect(homeTargets(["aia"], perms)).toEqual([AIA]);
  });

  it("ignoriert das Assistenten-Recht in einer reinen Werkzeug-Anlage", () => {
    const perms = { ...EMPTY_PERMS, allow_aia: true, tools: ["tts"] };
    expect(homeTargets(["tools"], perms)).toEqual([{ kind: "tool", key: "tts", href: "/tools/tts" }]);
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

describe("sichtbareWerkzeuge", () => {
  const allesAn = () => true;

  it("gibt nur Werkzeuge zurueck, fuer die Recht und Schalter da sind", () => {
    const perms = { ...EMPTY_PERMS, tools: ["tts", "screencast"] };
    const schalter = (key: string) => key !== "screencast";
    expect(sichtbareWerkzeuge(perms, schalter)).toEqual(["tts"]);
  });

  it("haelt die Reihenfolge der Uebersicht ein, nicht die der Rechte", () => {
    const perms = { ...EMPTY_PERMS, tools: ["glossary", "translation"] };
    expect(sichtbareWerkzeuge(perms, allesAn)).toEqual(["translation", "glossary"]);
  });

  it("gibt ohne jedes Recht nichts zurueck", () => {
    expect(sichtbareWerkzeuge(EMPTY_PERMS, allesAn)).toEqual([]);
  });
});

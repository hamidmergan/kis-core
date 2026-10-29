import { describe, it, expect } from "vitest";
import { resolvePreview } from "./_preview";

const ownerOf = { realIsOwner: true, isDemoWorkspace: false, darfModuleAnlegen: true, override: null };
const studentIn = { realIsOwner: false, isDemoWorkspace: false, darfModuleAnlegen: false, override: null };
const testerInDemo = { realIsOwner: false, isDemoWorkspace: true, darfModuleAnlegen: true, override: null };
const studentInDemo = { realIsOwner: false, isDemoWorkspace: true, darfModuleAnlegen: false, override: null };

describe("wer den Umschalter überhaupt bekommt", () => {
  it("Eigentümer bekommen ihn in jedem eigenen Modul", () => {
    expect(resolvePreview(ownerOf).canPreview).toBe(true);
  });

  it("Studierende in einem normalen Modul bekommen ihn nicht", () => {
    expect(resolvePreview(studentIn).canPreview).toBe(false);
  });

  it("Lehrende im Demo-Modul bekommen ihn", () => {
    expect(resolvePreview(testerInDemo).canPreview).toBe(true);
  });

  it("Studierende im Demo-Modul bekommen ihn nicht", () => {
    // The teacher view shows buttons this person never gets.
    expect(resolvePreview(studentInDemo).canPreview).toBe(false);
  });

  it("wer ein Modul besitzt, behält den Schalter auch ohne das Recht", () => {
    expect(resolvePreview({ ...ownerOf, darfModuleAnlegen: false }).canPreview).toBe(true);
  });
});

describe("Voreinstellung", () => {
  it("im Demo-Modul startet die Lehrenden-Vorschau eingeschaltet", () => {
    const s = resolvePreview(testerInDemo);
    expect(s.previewOn).toBe(true);
    expect(s.isOwner).toBe(true);
    expect(s.ownerPreview).toBe(true);
  });

  it("Studierende starten im Demo-Modul in ihrer eigenen Ansicht", () => {
    const s = resolvePreview(studentInDemo);
    expect(s.previewOn).toBe(false);
    expect(s.isOwner).toBe(false);
    expect(s.ownerPreview).toBe(false);
  });

  it("Eigentümer starten in ihrer normalen Ansicht", () => {
    const s = resolvePreview(ownerOf);
    expect(s.previewOn).toBe(false);
    expect(s.isOwner).toBe(true);
    expect(s.ownerPreview).toBe(false);
  });
});

describe("Umschalten", () => {
  it("Eigentümer in der Studierenden-Vorschau verlieren die Bedienelemente ganz", () => {
    const s = resolvePreview({ ...ownerOf, override: true });
    expect(s.isOwner).toBe(false);
    // Not marked but gone: this is what students really see.
    expect(s.ownerPreview).toBe(false);
  });

  it("Tester können die Lehrenden-Vorschau abschalten und sehen dann die echte Studierenden-Sicht", () => {
    const s = resolvePreview({ ...testerInDemo, override: false });
    expect(s.isOwner).toBe(false);
    expect(s.ownerPreview).toBe(false);
  });
});

describe("Sicherheit", () => {
  it("ohne Demo-Modul führt kein Schalter zu Owner-Elementen", () => {
    for (const override of [null, true, false]) {
      expect(resolvePreview({ ...studentIn, override }).isOwner).toBe(false);
    }
  });

  it("ohne das Recht Module anzulegen führt kein Schalter zu Owner-Elementen", () => {
    for (const override of [null, true, false]) {
      const s = resolvePreview({ ...studentInDemo, override });
      expect(s.isOwner).toBe(false);
      expect(s.ownerPreview).toBe(false);
    }
  });

  it("die markierte Vorschau gilt nie für echte Eigentümer", () => {
    for (const override of [null, true, false]) {
      expect(resolvePreview({ ...ownerOf, override }).ownerPreview).toBe(false);
    }
  });
});

describe("Beschriftung", () => {
  it("Eigentümer schauen auf die Studierenden-Seite, Tester auf die Lehrenden-Seite", () => {
    expect(resolvePreview(ownerOf).previewsOwnerSide).toBe(false);
    expect(resolvePreview(testerInDemo).previewsOwnerSide).toBe(true);
  });
});

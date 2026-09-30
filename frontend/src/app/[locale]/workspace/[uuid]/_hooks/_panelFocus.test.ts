import { describe, it, expect } from "vitest";
import { nextFocusLayout } from "./_panelFocus";

const ALL: ("quellen" | "chat" | "studio")[] = ["quellen", "chat", "studio"];

describe("nextFocusLayout", () => {
  it("zeigt das Panel allein und merkt sich die Aufteilung davor", () => {
    const before = { quellen: true, chat: true, studio: false };
    const r = nextFocusLayout(before, "chat", null, ALL);
    expect(r.panels).toEqual({ quellen: false, chat: true, studio: false });
    expect(r.saved).toEqual(before);
  });

  it("stellt beim zweiten Doppelklick die gemerkte Aufteilung wieder her", () => {
    const before = { quellen: true, chat: true, studio: false };
    const first = nextFocusLayout(before, "chat", null, ALL);
    const second = nextFocusLayout(first.panels, "chat", first.saved, ALL);
    expect(second.panels).toEqual(before);
    expect(second.saved).toBeNull();
  });

  it("öffnet alle, wenn das Panel schon allein offen ist und nichts gemerkt wurde", () => {
    const r = nextFocusLayout({ quellen: false, chat: false, studio: true }, "studio", null, ALL);
    expect(r.panels).toEqual({ quellen: true, chat: true, studio: true });
  });

  it("merkt sich nach einer Handänderung die Aufteilung direkt vor dem Doppelklick", () => {
    const first = nextFocusLayout({ quellen: true, chat: true, studio: true }, "chat", null, ALL);
    // The studio strip was opened by hand, now the studio header gets the double click.
    const opened = { ...first.panels, studio: true };
    const second = nextFocusLayout(opened, "studio", first.saved, ALL);
    expect(second.panels).toEqual({ quellen: false, chat: false, studio: true });
    expect(nextFocusLayout(second.panels, "studio", second.saved, ALL).panels).toEqual(opened);
  });

  it("lässt ein ausgeblendetes Studio unberührt", () => {
    const visible: ("quellen" | "chat" | "studio")[] = ["quellen", "chat"];
    const before = { quellen: true, chat: true, studio: true };
    const first = nextFocusLayout(before, "quellen", null, visible);
    expect(first.panels).toEqual({ quellen: true, chat: false, studio: true });
    expect(nextFocusLayout(first.panels, "quellen", first.saved, visible).panels).toEqual(before);
  });
});

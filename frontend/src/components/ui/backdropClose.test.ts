import { describe, expect, it } from "vitest";

import { backdropClose, newBackdropPress } from "./backdropClose";

/** An event as React delivers it: what was pressed and where the handle sits. */
function ereignis(target: unknown, currentTarget: unknown) {
  return { target, currentTarget } as never;
}

const HINTERGRUND = { name: "hintergrund" };
const FELD = { name: "eingabefeld" };

describe("backdropClose", () => {
  it("schliesst beim Klick auf den Hintergrund", () => {
    let zu = false;
    const h = backdropClose(newBackdropPress(), () => { zu = true; });
    h.onMouseDown(ereignis(HINTERGRUND, HINTERGRUND));
    h.onClick(ereignis(HINTERGRUND, HINTERGRUND));
    expect(zu).toBe(true);
  });

  it("bleibt offen, wenn das Markieren im Feld begann und daneben endete", () => {
    // Exactly the annoying case: the click lands on the shared parent.
    let zu = false;
    const h = backdropClose(newBackdropPress(), () => { zu = true; });
    h.onMouseDown(ereignis(FELD, HINTERGRUND));
    h.onClick(ereignis(HINTERGRUND, HINTERGRUND));
    expect(zu).toBe(false);
  });

  it("bleibt offen, wenn der Klick den Inhalt trifft", () => {
    let zu = false;
    const h = backdropClose(newBackdropPress(), () => { zu = true; });
    h.onMouseDown(ereignis(FELD, HINTERGRUND));
    h.onClick(ereignis(FELD, HINTERGRUND));
    expect(zu).toBe(false);
  });

  it("vergisst den vorherigen Griff nicht bis zum naechsten Druck", () => {
    // After a selection a real click outside has to close again.
    let zu = 0;
    const press = newBackdropPress();
    const h = backdropClose(press, () => { zu += 1; });
    h.onMouseDown(ereignis(FELD, HINTERGRUND));
    h.onClick(ereignis(HINTERGRUND, HINTERGRUND));
    h.onMouseDown(ereignis(HINTERGRUND, HINTERGRUND));
    h.onClick(ereignis(HINTERGRUND, HINTERGRUND));
    expect(zu).toBe(1);
  });

  it("schliesst nicht, solange es abgeschaltet ist", () => {
    // For dialogs that must not go away while saving.
    let zu = false;
    const press = newBackdropPress();
    const h = backdropClose(press, () => { zu = true; }, false);
    h.onMouseDown(ereignis(HINTERGRUND, HINTERGRUND));
    h.onClick(ereignis(HINTERGRUND, HINTERGRUND));
    expect(zu).toBe(false);
  });
});

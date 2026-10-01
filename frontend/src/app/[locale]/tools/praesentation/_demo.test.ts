import { describe, expect, it } from "vitest";
import type { PraesentationView } from "./_api";
import { demoAblauf } from "./_demo";
import type { Slide } from "./_types";

const folie = (id: string): Slide =>
  ({ id, role: "text", layout: 1, title: id, subtitle: "", body: null, columns: [], images: [{ prompt: "p" }], notes: "" });

const view: PraesentationView = {
  job_uuid: "demo", status: "success", progress: null, error: null, params: null,
  outline: { title: "D", subtitle: "", rows: [{ id: "s1", role: "text", title: "A", gist: "" }, { id: "s2", role: "text", title: "B", gist: "" }] },
  slides: [folie("s1"), folie("s2")],
  previews: ["s1", "s2"], images: { s1: ["0"], s2: ["0"] }, missing_images: [], has_deck: true,
};

describe("demoAblauf", () => {
  const momente = demoAblauf(view);

  it("geht die Schritte eines echten Laufs in ihrer Reihenfolge durch", () => {
    expect(momente.map((m) => m.progress?.step ?? null)).toEqual(
      ["material", "outline", "texte", "texte", "bilder", "bilder", "vorschau", null]);
  });

  it("schreibt Folie für Folie und zeichnet Bild für Bild", () => {
    expect(momente[2].stand.slides.map((s) => s.id)).toEqual(["s1"]);
    expect(momente[3].stand.slides.map((s) => s.id)).toEqual(["s1", "s2"]);
    expect(momente[4].stand.images).toEqual({ s1: ["0"] });
    expect(momente[5].stand.images).toEqual({ s1: ["0"], s2: ["0"] });
  });

  it("zeigt die Vorschaubilder erst am Ende und wartet dann auf die Person", () => {
    expect(momente.slice(0, -1).every((m) => m.stand.previews.length === 0)).toBe(true);
    const ende = momente[momente.length - 1];
    expect(ende.status).toBe("awaiting_user");
    expect(ende.stand.previews).toEqual(["s1", "s2"]);
    expect(ende.stand.hasDeck).toBe(true);
  });
});

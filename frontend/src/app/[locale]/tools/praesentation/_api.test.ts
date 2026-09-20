import { afterEach, describe, expect, it, vi } from "vitest";
import { fehlerText, insertSlide, setNotesInclude } from "./_api";

const antwort = (body: unknown) => new Response(JSON.stringify(body), { status: 422 });

describe("fehlerText", () => {
  it("liest eine einfache Fehlermeldung", async () => {
    expect(await fehlerText(antwort({ detail: "kaputt" }))).toBe("kaputt");
  });
  it("nimmt bei einer Validierungsliste die erste Meldung", async () => {
    const body = { detail: [{ loc: ["body", "notes"], msg: "String should have at most 1500 characters", type: "string_too_long" }] };
    expect(await fehlerText(antwort(body))).toBe("String should have at most 1500 characters");
  });
  it("liefert leer ohne lesbares Detail", async () => {
    expect(await fehlerText(antwort({ detail: [{ type: "string_too_long" }] }))).toBe("");
    expect(await fehlerText(antwort({}))).toBe("");
  });
});

describe("insertSlide", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("schickt Titel und Anweisung mit", async () => {
    const gesehen: { url: string; body: unknown }[] = [];
    vi.stubGlobal("fetch", (url: string, init: RequestInit) => {
      gesehen.push({ url, body: JSON.parse(String(init.body)) });
      return Promise.resolve(new Response(JSON.stringify({ id: "s7" }), { status: 200 }));
    });
    await insertSlide("abc", "s2", "Kühlung", "nur die Zahlen aus Kapitel 4");
    expect(gesehen[0].url).toBe("/api/praesentation/abc/slides");
    expect(gesehen[0].body).toEqual({ after: "s2", title: "Kühlung", instruction: "nur die Zahlen aus Kapitel 4" });
  });
});

describe("setNotesInclude", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("schickt den Schalter als Ja oder Nein", async () => {
    const gesehen: { url: string; method?: string; body: unknown }[] = [];
    vi.stubGlobal("fetch", (url: string, init: RequestInit) => {
      gesehen.push({ url, method: init.method, body: JSON.parse(String(init.body)) });
      return Promise.resolve(new Response(JSON.stringify({ include: false }), { status: 200 }));
    });
    await setNotesInclude("abc", false);
    expect(gesehen[0].url).toBe("/api/praesentation/abc/notes");
    expect(gesehen[0].method).toBe("PUT");
    expect(gesehen[0].body).toEqual({ include: false });
  });
});

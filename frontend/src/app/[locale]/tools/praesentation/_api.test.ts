import { afterEach, describe, expect, it, vi } from "vitest";
import { fehlerText, insertSlide, setNotesInclude, startPraesentation } from "./_api";
import { INITIAL_STATE } from "./_reducer";

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

describe("startPraesentation", () => {
  afterEach(() => vi.unstubAllGlobals());

  const gesendet = async (imageStyle: string | null) => {
    let params: Record<string, unknown> = {};
    vi.stubGlobal("fetch", (_url: string, init: RequestInit) => {
      params = JSON.parse(String((init.body as FormData).get("params")));
      return Promise.resolve(new Response(JSON.stringify({ job_uuid: "j1" }), { status: 200 }));
    });
    await startPraesentation({ ...INITIAL_STATE, imageStyle }, null);
    return params;
  };

  it("laesst den Bildstil weg, solange er nicht angefasst wurde", async () => {
    expect(await gesendet(null)).not.toHaveProperty("style_text");
  });
  it("schickt einen geaenderten Bildstil mit, auch einen leeren", async () => {
    expect((await gesendet("Watercolour, soft blue")).style_text).toBe("Watercolour, soft blue");
    expect((await gesendet("")).style_text).toBe("");
  });
});

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { backendApi as BackendApi } from "./api";

// The client only ever leaves a page once, so every test needs its own module copy.
let backendApi: typeof BackendApi;

beforeEach(async () => {
  vi.resetModules();
  backendApi = (await import("./api")).backendApi;
});

// A window stub, only the parts the client reads.
function fensterMit(pathname: string) {
  const location = { pathname, href: "unveraendert" };
  vi.stubGlobal("window", { location });
  return location;
}

function antwort(status: number, body: unknown) {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
    new Response(JSON.stringify(body), {
      status,
      headers: { "Content-Type": "application/json" },
    }),
  ));
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("403 aus dem Zugangsende", () => {
  it("schickt auf die Anmeldeseite mit Hinweis", async () => {
    const ort = fensterMit("/tools/translation");
    antwort(403, { detail: "access_expired" });

    await backendApi.fetch("/aia/workspaces");

    expect(ort.href).toBe("/login?expired=1");
  });

  it("laesst die Antwort trotzdem lesbar", async () => {
    fensterMit("/tools/translation");
    antwort(403, { detail: "access_expired" });

    const r = await backendApi.fetch("/aia/workspaces");

    expect(await r.json()).toEqual({ detail: "access_expired" });
  });

  it("schickt nicht nochmal, wenn die Anmeldeseite schon offen ist", async () => {
    const ort = fensterMit("/login");
    antwort(403, { detail: "access_expired" });

    await backendApi.fetch("/aia/workspaces");

    expect(ort.href).toBe("unveraendert");
  });

  it("schickt auch aus der englischen Anmeldeseite nicht nochmal", async () => {
    const ort = fensterMit("/en/login");
    antwort(403, { detail: "access_expired" });

    await backendApi.fetch("/aia/workspaces");

    expect(ort.href).toBe("unveraendert");
  });

  it("laesst sich vom nachlaufenden 401 nicht ueberschreiben", async () => {
    const ort = fensterMit("/");
    antwort(403, { detail: "access_expired" });
    await backendApi.fetch("/aia/workspaces");

    antwort(401, { detail: "not authenticated" });
    await backendApi.fetch("/aia/tools");

    expect(ort.href).toBe("/login?expired=1");
  });

  it("laesst die Verlaengern-Seite in Ruhe", async () => {
    const ort = fensterMit("/redeem/expired");
    antwort(403, { detail: "access_expired" });

    await backendApi.fetch("/aia/workspaces");

    expect(ort.href).toBe("unveraendert");
  });
});

describe("jedes andere 403", () => {
  it("bleibt ein einfacher Fehler", async () => {
    const ort = fensterMit("/admin");
    antwort(403, { detail: "Keine Berechtigung" });

    const r = await backendApi.fetch("/admin/users");

    expect(r.status).toBe(403);
    expect(ort.href).toBe("unveraendert");
  });

  it("stolpert nicht ueber einen Koerper ohne JSON", async () => {
    const ort = fensterMit("/admin");
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("nope", { status: 403 })));

    const r = await backendApi.fetch("/admin/users");

    expect(r.status).toBe(403);
    expect(ort.href).toBe("unveraendert");
  });
});

describe("401 on the login page", () => {
  it("stays on the German login page so the wrong password shows", async () => {
    const ort = fensterMit("/login");
    antwort(401, { detail: "wrong" });

    await backendApi.fetch("/auth/login");

    expect(ort.href).toBe("unveraendert");
  });

  it("stays on the English login page as well", async () => {
    const ort = fensterMit("/en/login");
    antwort(401, { detail: "wrong" });

    await backendApi.fetch("/auth/login");

    expect(ort.href).toBe("unveraendert");
  });

  it("still sends every other page to the login", async () => {
    const ort = fensterMit("/en/tools/tts");
    antwort(401, { detail: "not authenticated" });

    await backendApi.fetch("/aia/workspaces");

    expect(ort.href).toBe("/login");
  });
});

describe("file name from the header", () => {
  it("decodes the UTF-8 form", async () => {
    const { filenameFromDisposition } = await import("./api");
    expect(filenameFromDisposition("attachment; filename*=UTF-8''%C3%9Cbung.pdf", "x")).toBe("Übung.pdf");
  });

  it("keeps a plain name with a bare percent sign", async () => {
    const { filenameFromDisposition } = await import("./api");
    expect(filenameFromDisposition('attachment; filename="100% fertig.pdf"', "x")).toBe("100% fertig.pdf");
  });

  it("falls back without a header", async () => {
    const { filenameFromDisposition } = await import("./api");
    expect(filenameFromDisposition(null, "output")).toBe("output");
  });
});

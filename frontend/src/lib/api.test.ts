import { afterEach, describe, expect, it, vi } from "vitest";
import { backendApi } from "./api";

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
  it("schickt auf die Abgelaufen-Seite", async () => {
    const ort = fensterMit("/tools/translation");
    antwort(403, { detail: "access_expired" });

    await backendApi.fetch("/aia/workspaces");

    expect(ort.href).toBe("/zugang/abgelaufen");
  });

  it("laesst die Antwort trotzdem lesbar", async () => {
    fensterMit("/tools/translation");
    antwort(403, { detail: "access_expired" });

    const r = await backendApi.fetch("/aia/workspaces");

    expect(await r.json()).toEqual({ detail: "access_expired" });
  });

  it("schickt nicht nochmal, wenn die Seite schon offen ist", async () => {
    const ort = fensterMit("/zugang/abgelaufen");
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

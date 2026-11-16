import { describe, expect, it } from "vitest";
import type { AuthStatus, UserPermissions } from "@/types";
import { EMPTY_PERMS } from "@/lib/permissions";
import { redirectFor } from "./_routeGuard";

const signedIn = (perms: Partial<UserPermissions> = {}, modules?: string[]): AuthStatus => ({
  authenticated: true,
  permissions: { ...EMPTY_PERMS, ...perms },
  modules,
});

describe("redirectFor", () => {
  it("sends a guest to the login, back to a shared page afterwards", () => {
    expect(redirectFor({ authenticated: false }, "/workspace")).toBe("/login");
    expect(redirectFor({ authenticated: false }, "/p/abc123")).toBe("/login?next=%2Fp%2Fabc123");
    expect(redirectFor({ authenticated: false, reason: "access_expired" }, "/p/abc123")).toBe("/login?expired=1");
  });

  it("keeps the workspaces for accounts with the assistant", () => {
    expect(redirectFor(signedIn({ allow_aia: true }), "/workspace/x")).toBeNull();
    expect(redirectFor(signedIn(), "/workspace")).toBe("/services");
    expect(redirectFor(signedIn({ allow_aia: true }, ["tools"]), "/workspace")).toBe("/services");
  });

  it("checks the tool behind the path", () => {
    expect(redirectFor(signedIn({ tools: ["transcription"] }), "/tools/stt")).toBeNull();
    expect(redirectFor(signedIn({ tools: ["tts"] }), "/tools/stt")).toBe("/workspace");
    expect(redirectFor(signedIn({ tools: ["campus"] }), "/tools/info")).toBeNull();
    // A page below /tools without a tool of its own is open to every account.
    expect(redirectFor(signedIn(), "/tools/screencast-demo")).toBeNull();
  });

  it("guards calendar, admin, manual and jobs", () => {
    expect(redirectFor(signedIn({}, ["tools"]), "/calendar")).toBe("/services");
    expect(redirectFor(signedIn(), "/calendar")).toBeNull();
    expect(redirectFor(signedIn(), "/admin/users")).toBe("/workspace");
    expect(redirectFor(signedIn({ allow_admin_panel: true }), "/admin/users")).toBeNull();
    expect(redirectFor(signedIn(), "/manual")).toBe("/workspace");
    expect(redirectFor(signedIn({ keys: ["general.manual"] }), "/manual")).toBeNull();
    expect(redirectFor(signedIn(), "/my-jobs")).toBe("/workspace");
    expect(redirectFor(signedIn({ tools: ["tts"] }), "/my-jobs")).toBeNull();
  });
});

import { describe, it, expect } from "vitest";
import { roleToPayload } from "./useRoleOptions";

describe("roleToPayload", () => {
  it("passes a system role through", () => {
    expect(roleToPayload("staff")).toEqual({ kis_role: "staff", custom_role_id: null });
    expect(roleToPayload("user")).toEqual({ kis_role: "user", custom_role_id: null });
  });

  it("splits a custom role into kind and id", () => {
    expect(roleToPayload("custom:7")).toEqual({ kis_role: "custom", custom_role_id: 7 });
  });
});

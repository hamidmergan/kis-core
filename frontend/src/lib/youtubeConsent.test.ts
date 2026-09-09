import { afterEach, describe, expect, it, vi } from "vitest";
import { readYoutubeConsent, writeYoutubeConsent } from "./youtubeConsent";

// A localStorage stub backed by a plain map, only get/set are used.
function stubStorage() {
  const store = new Map<string, string>();
  vi.stubGlobal("window", {});
  vi.stubGlobal("localStorage", {
    getItem: (key: string) => store.get(key) ?? null,
    setItem: (key: string, value: string) => { store.set(key, value); },
  });
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("readYoutubeConsent", () => {
  it("is false without a stored decision", () => {
    stubStorage();
    expect(readYoutubeConsent()).toBe(false);
  });

  it("is true once writeYoutubeConsent ran", () => {
    stubStorage();
    writeYoutubeConsent();
    expect(readYoutubeConsent()).toBe(true);
  });

  it("is false outside the browser", () => {
    expect(readYoutubeConsent()).toBe(false);
  });
});

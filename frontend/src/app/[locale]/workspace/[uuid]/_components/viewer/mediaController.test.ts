import { describe, it, expect } from "vitest";
import { htmlMediaController } from "./mediaController";

class FakeMedia {
  currentTime = 0;
  played = 0;
  private listeners = new Map<string, Set<() => void>>();
  addEventListener(type: string, cb: () => void) {
    if (!this.listeners.has(type)) this.listeners.set(type, new Set());
    this.listeners.get(type)!.add(cb);
  }
  removeEventListener(type: string, cb: () => void) {
    this.listeners.get(type)?.delete(cb);
  }
  play() {
    this.played += 1;
    return Promise.resolve();
  }
  fire(type: string) {
    this.listeners.get(type)?.forEach((cb) => cb());
  }
  count(type: string) {
    return this.listeners.get(type)?.size ?? 0;
  }
}

const asMedia = (m: FakeMedia) => m as unknown as HTMLMediaElement;

describe("htmlMediaController", () => {
  it("reads and sets the time and plays", () => {
    const media = new FakeMedia();
    const c = htmlMediaController(asMedia(media));
    media.currentTime = 12.5;
    expect(c.currentTime()).toBe(12.5);
    c.seek(40);
    expect(media.currentTime).toBe(40);
    c.play();
    expect(media.played).toBe(1);
  });

  it("forwards timeupdate and unsubscribes", () => {
    const media = new FakeMedia();
    const c = htmlMediaController(asMedia(media));
    let ticks = 0;
    const stop = c.onTime(() => { ticks += 1; });
    media.fire("timeupdate");
    media.fire("timeupdate");
    expect(ticks).toBe(2);
    stop();
    media.fire("timeupdate");
    expect(ticks).toBe(2);
    expect(media.count("timeupdate")).toBe(0);
  });
});

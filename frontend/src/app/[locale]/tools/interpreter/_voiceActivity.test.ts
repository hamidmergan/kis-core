import { describe, expect, it } from "vitest";
import { createVoiceTracker, SPEECH_LEVEL } from "./_voiceActivity";

function clock(start = 1000) {
  let t = start;
  return { now: () => t, advance: (ms: number) => (t += ms) };
}

describe("Stimme am Mikrofon", () => {
  it("merkt sich eine Stimme und vergisst sie nach dem Abholen", () => {
    const tracker = createVoiceTracker();
    expect(tracker.takeHeard()).toBe(false);
    tracker.sample(SPEECH_LEVEL * 2);
    expect(tracker.takeHeard()).toBe(true);
    expect(tracker.takeHeard()).toBe(false);
  });

  it("zählt leise Werte nicht als Stimme", () => {
    const tracker = createVoiceTracker();
    tracker.sample(SPEECH_LEVEL / 2);
    tracker.sample(0);
    expect(tracker.takeHeard()).toBe(false);
    expect(tracker.everHeard()).toBe(false);
  });

  it("zählt die Stille ab der letzten Stimme", () => {
    const c = clock();
    const tracker = createVoiceTracker(c.now);
    c.advance(5000);
    expect(tracker.quietMs()).toBe(5000);

    tracker.sample(SPEECH_LEVEL);
    expect(tracker.quietMs()).toBe(0);
    c.advance(30000);
    expect(tracker.quietMs()).toBe(30000);
    expect(tracker.everHeard()).toBe(true);
  });
});

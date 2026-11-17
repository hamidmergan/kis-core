import { describe, expect, it } from "vitest";
import { fmtTs, parseVtt } from "./_vtt";

describe("parseVtt", () => {
  it("reads cues with and without hours, joining text lines", () => {
    const raw = "WEBVTT\n\n1\n00:01.500 --> 00:03.000\nfirst\nline\n\n01:00:02,250 --> 01:00:04.000 align:start\nsecond\n";
    expect(parseVtt(raw)).toEqual([
      { start: 1.5, end: 3, text: "first line" },
      { start: 3602.25, end: 3604, text: "second" },
    ]);
  });

  it("skips a cue without text or with a broken time", () => {
    const raw = "WEBVTT\r\n\r\n00:01.000 --> 00:02.000\r\n\r\nxx --> 00:05.000\r\nlost\r\n\r\n00:06.000 --> 00:07.000\r\nkept\r\n";
    expect(parseVtt(raw)).toEqual([{ start: 6, end: 7, text: "kept" }]);
  });
});

describe("fmtTs", () => {
  it("shows the hours only once there are any", () => {
    expect(fmtTs(0)).toBe("00:00");
    expect(fmtTs(75.9)).toBe("01:15");
    expect(fmtTs(3725)).toBe("1:02:05");
  });
});

import { describe, expect, it } from "vitest";
import { AI_HINWEIS_TEXT } from "@/lib/constants";
import { stripAiNoticeText, stripAiNoticeVtt, withAiNoticeText, withAiNoticeVtt } from "./aiNotice";

describe("plain text notice", () => {
  it("adds the notice as a leading line", () => {
    expect(withAiNoticeText("Hallo Welt")).toBe(`${AI_HINWEIS_TEXT}\n\nHallo Welt`);
  });

  it("strips a notice that was added", () => {
    const withNotice = withAiNoticeText("Hallo Welt");
    expect(stripAiNoticeText(withNotice)).toBe("Hallo Welt");
  });

  it("leaves text without the notice untouched", () => {
    expect(stripAiNoticeText("Hallo Welt")).toBe("Hallo Welt");
  });
});

describe("vtt notice", () => {
  const vtt = "WEBVTT\n\n00:00:00.000 --> 00:00:01.000\nHallo\n";

  it("inserts a single-line NOTE right after the header", () => {
    const result = withAiNoticeVtt(vtt);
    expect(result).toBe(`WEBVTT\n\nNOTE ${AI_HINWEIS_TEXT}\n\n00:00:00.000 --> 00:00:01.000\nHallo\n`);
  });

  it("round-trips: stripping what was added returns the original", () => {
    expect(stripAiNoticeVtt(withAiNoticeVtt(vtt))).toBe(vtt);
  });

  it("leaves vtt text without the notice untouched", () => {
    expect(stripAiNoticeVtt(vtt)).toBe(vtt);
  });

  it("leaves non-vtt text untouched", () => {
    expect(withAiNoticeVtt("not a vtt file")).toBe("not a vtt file");
  });
});

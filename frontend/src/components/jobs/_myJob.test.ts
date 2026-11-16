import { describe, expect, it } from "vitest";
import { canRetry, downloadFormat, isExpired } from "./_myJob";
import { openJumps, resumeHref } from "./_jobJump";

const job = (tool: string, status: string, extra: Record<string, unknown> = {}) =>
  ({ job_uuid: "u1", tool, status, has_download: true, result_filename: null, ...extra }) as never;

describe("downloadFormat", () => {
  it("names the fixed formats", () => {
    expect(downloadFormat(job("screencast_render", "success"))).toBe("MP4");
    expect(downloadFormat(job("screencast_auto", "success"))).toBe("MP4");
    expect(downloadFormat(job("screencast_translate", "success"))).toBe("MP4");
    expect(downloadFormat(job("image_generate", "success"))).toBe("PNG");
    expect(downloadFormat(job("image_edit", "success"))).toBe("PNG");
    expect(downloadFormat(job("image_analyze", "success"))).toBe("TXT");
    expect(downloadFormat(job("tts", "success"))).toBe("MP3");
  });

  it("reads the format off the file name where it varies", () => {
    expect(downloadFormat(job("translation", "success", { result_filename: "a.b.docx" }))).toBe("DOCX");
    expect(downloadFormat(job("summary", "success"))).toBeNull();
  });

  it("has no format for any other tool", () => {
    expect(downloadFormat(job("podcast", "success", { result_filename: "a.mp3" }))).toBeNull();
  });
});

describe("canRetry", () => {
  it("offers failed and paused jobs of the three direct tools", () => {
    expect(canRetry(job("tts", "failed"))).toBe(true);
    expect(canRetry(job("screencast_render", "paused"))).toBe(true);
    expect(canRetry(job("screencast_translate", "running"))).toBe(false);
  });

  it("offers summary and pages only while paused", () => {
    expect(canRetry(job("summary", "paused"))).toBe(true);
    expect(canRetry(job("pages", "failed"))).toBe(false);
    expect(canRetry(job("podcast", "failed"))).toBe(false);
  });
});

describe("isExpired", () => {
  it("is a finished job without its files", () => {
    expect(isExpired(job("tts", "success", { has_download: false }))).toBe(true);
    expect(isExpired(job("tts", "success"))).toBe(false);
    expect(isExpired(job("tts", "failed", { has_download: false }))).toBe(false);
  });
});

describe("jumps", () => {
  it("continues a waiting job on its own page", () => {
    expect(resumeHref(job("podcast", "awaiting_user"))).toBe("/tools/podcast?job=u1");
    expect(resumeHref(job("praesentation", "paused"))).toBe("/tools/praesentation?job=u1");
    expect(resumeHref(job("screencast_translate", "awaiting_user"))).toBe("/tools/screencast?resume=u1");
    expect(resumeHref(job("tts", "failed"))).toBeUndefined();
  });

  it("opens a finished job in its tool", () => {
    expect(openJumps(job("tts", "success"))).toEqual([{ href: "/tools/tts?job=u1", label: "openTts" }]);
    expect(openJumps(job("pages", "success"))).toEqual([{ href: "/tools/pages/u1", label: "openPage" }]);
    expect(openJumps(job("image_edit", "success"))).toEqual([{ href: "/tools/image?job=u1", label: "openImage" }]);
    expect(openJumps(job("tts", "success", { has_download: false }))).toEqual([]);
  });
});

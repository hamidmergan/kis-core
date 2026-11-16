import { describe, it, expect } from "vitest";
import { checkUpload } from "./uploadCheck";

const EXTS = [".docx", ".md"];

describe("checkUpload", () => {
  it("accepts an allowed file within the size limit", () => {
    expect(checkUpload({ name: "skript.docx", size: 10 }, EXTS, 100)).toBeNull();
  });

  it("ignores the case of the extension", () => {
    expect(checkUpload({ name: "SKRIPT.MD", size: 10 }, EXTS, 100)).toBeNull();
  });

  it("rejects an extension that is not listed", () => {
    expect(checkUpload({ name: "skript.pdf", size: 10 }, EXTS, 100)).toBe("extension");
  });

  it("rejects a file without extension", () => {
    expect(checkUpload({ name: "skript", size: 10 }, EXTS, 100)).toBe("extension");
  });

  it("accepts a file exactly at the size limit", () => {
    expect(checkUpload({ name: "a.md", size: 100 }, EXTS, 100)).toBeNull();
  });

  it("rejects a file above the size limit", () => {
    expect(checkUpload({ name: "a.md", size: 101 }, EXTS, 100)).toBe("size");
  });

  it("reports the extension before the size", () => {
    expect(checkUpload({ name: "a.pdf", size: 101 }, EXTS, 100)).toBe("extension");
  });
});

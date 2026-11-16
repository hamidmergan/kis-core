import { afterEach, describe, expect, it, vi } from "vitest";
import { triggerBlobDownload, triggerUrlDownload } from "./download";

interface FakeLink {
  href: string;
  download: string;
  click: () => void;
}

// A document stub that records what happened to the one link each helper creates.
function stubDocument() {
  const log: string[] = [];
  const link: FakeLink = { href: "", download: "", click: () => log.push("click") };
  vi.stubGlobal("document", {
    createElement: (tag: string) => {
      log.push(`create:${tag}`);
      return link;
    },
    body: {
      appendChild: () => log.push("append"),
      removeChild: () => log.push("remove"),
    },
  });
  return { log, link };
}

afterEach(() => vi.unstubAllGlobals());

describe("triggerUrlDownload", () => {
  it("clicks a link to the address without putting it into the page", () => {
    const { log, link } = stubDocument();
    triggerUrlDownload("/api/jobs/abc/download");
    expect(link.href).toBe("/api/jobs/abc/download");
    expect(link.download).toBe("");
    expect(log).toEqual(["create:a", "click"]);
  });

  it("passes the file name on when one is given", () => {
    const { link } = stubDocument();
    triggerUrlDownload("/api/podcast/abc/transcript", "podcast.txt");
    expect(link.download).toBe("podcast.txt");
  });
});

describe("triggerBlobDownload", () => {
  it("clicks a link to the blob and releases the address afterwards", () => {
    const { log, link } = stubDocument();
    const revoked: string[] = [];
    vi.stubGlobal("URL", {
      createObjectURL: () => "blob:test",
      revokeObjectURL: (url: string) => revoked.push(url),
    });
    triggerBlobDownload(new Blob(["x"]), "deck.pptx");
    expect(link.href).toBe("blob:test");
    expect(link.download).toBe("deck.pptx");
    expect(log).toEqual(["create:a", "append", "click", "remove"]);
    expect(revoked).toEqual(["blob:test"]);
  });
});

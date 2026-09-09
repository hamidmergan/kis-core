import { describe, it, expect } from "vitest";
import { isYoutubeSource, youtubeVideoId } from "./youtube";

const ID = "dQw4w9WgXcQ";

describe("youtubeVideoId", () => {
  it.each([
    `https://www.youtube.com/watch?v=${ID}`,
    `https://youtube.com/watch?v=${ID}&t=42s`,
    `https://m.youtube.com/watch?feature=share&v=${ID}`,
    `https://youtu.be/${ID}`,
    `https://youtu.be/${ID}?si=abc`,
    `https://www.youtube.com/shorts/${ID}`,
    `https://www.youtube.com/live/${ID}`,
    `https://www.youtube-nocookie.com/embed/${ID}`,
    `youtu.be/${ID}`,
    `  https://www.youtube.com/watch?v=${ID}  `,
    `youtu.be/${ID}?redirect=http://evil.com`,
  ])("reads the id from %s", (link) => {
    expect(youtubeVideoId(link)).toBe(ID);
  });

  it.each([
    "",
    null,
    undefined,
    "https://vimeo.com/12345",
    "https://www.youtube.com/watch",
    "https://www.youtube.com/watch?v=kurz",
    "https://www.youtube.com/playlist?list=PLabc",
    `https://youtube.com.evil.example/watch?v=${ID}`,
    "javascript:alert(1)",
  ])("is null for %s", (link) => {
    expect(youtubeVideoId(link)).toBeNull();
  });
});

describe("isYoutubeSource", () => {
  it("looks at the extension only", () => {
    expect(isYoutubeSource("Vorlesung 3.youtube")).toBe(true);
    expect(isYoutubeSource("Vorlesung 3.YOUTUBE")).toBe(true);
    expect(isYoutubeSource("Vorlesung 3.mp4")).toBe(false);
  });
});

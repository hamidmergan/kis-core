// The same link rules as the backend, so the browser never shows a player for a link the server refused.
const HOSTS = new Set([
  "youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com",
  "www.youtube-nocookie.com", "youtu.be",
]);
const VIDEO_ID = /^[A-Za-z0-9_-]{11}$/;
const PATH_PREFIXES = new Set(["shorts", "live", "embed"]);
const LEADING_SCHEME = /^[a-z][a-z0-9+.-]*:\/\//i;

/** The 11-character id of a YouTube link, null when the link is no video. */
export function youtubeVideoId(raw: string | null | undefined): string | null {
  const text = (raw ?? "").trim();
  if (!text) return null;
  let url: URL;
  try {
    url = new URL(LEADING_SCHEME.test(text) ? text : `https://${text}`);
  } catch {
    return null;
  }
  if (url.protocol !== "https:" && url.protocol !== "http:") return null;
  const host = url.hostname.toLowerCase();
  if (!HOSTS.has(host)) return null;
  const segments = url.pathname.split("/").filter(Boolean);
  let candidate = "";
  if (host === "youtu.be") candidate = segments[0] ?? "";
  else if (segments.length >= 2 && PATH_PREFIXES.has(segments[0])) candidate = segments[1];
  else if (segments.length === 1 && segments[0] === "watch") candidate = url.searchParams.get("v") ?? "";
  return VIDEO_ID.test(candidate) ? candidate : null;
}

/** A YouTube source is told apart by its name, like every other kind. */
export function isYoutubeSource(filename: string): boolean {
  return filename.toLowerCase().endsWith(".youtube");
}

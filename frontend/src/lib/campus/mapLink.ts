/** The map link in the viewer's language, optionally jumping straight to one place. */
export function mapLink(mapUrl: string, locale: string, show?: string): string {
  let url: URL;
  try {
    url = new URL(mapUrl);
  } catch {
    return mapUrl;
  }
  url.searchParams.set("lang", locale);
  if (show) url.searchParams.set("show", show);
  return url.toString();
}

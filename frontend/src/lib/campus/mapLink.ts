/** The map link in the viewer's language, optionally jumping straight to one place. */
export function mapLink(mapUrl: string, locale: string, show?: string, partner?: { home: string; back: string }): string {
  let url: URL;
  try {
    url = new URL(mapUrl);
  } catch {
    return mapUrl;
  }
  url.searchParams.set("lang", locale);
  if (show) url.searchParams.set("show", show);
  if (partner) {
    url.searchParams.set("partner", "kis");
    url.searchParams.set("home", partner.home);
    url.searchParams.set("back", partner.back);
  }
  return url.toString();
}

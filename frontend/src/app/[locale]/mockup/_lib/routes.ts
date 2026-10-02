export const ROUTES = {
  overview: "/mockup",
  info: "/mockup/info",
  stamp: "/mockup/stempelkarte",
  admin: "/mockup/stempelkarte/admin",
  login: "/login",
  redeem: (code: string) => `/redeem?code=${encodeURIComponent(code)}`,
} as const;

export function stationQrUrl(origin: string, stationId: string): string {
  return `${origin}${ROUTES.stamp}?stand=${encodeURIComponent(stationId)}`;
}

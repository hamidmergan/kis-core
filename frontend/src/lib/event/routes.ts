export const ROUTES = {
  info: "/",
  stamp: "/stempelkarte",
  withdraw: "/raffle/withdraw",
  home: "/workspace",
  redeem: (code: string) => `/redeem?code=${encodeURIComponent(code)}`,
} as const;

export function stationQrUrl(origin: string, stationId: string): string {
  return `${origin}${ROUTES.stamp}?stand=${encodeURIComponent(stationId)}`;
}

/** The public landing page the landing poster leads to. */
export function landingUrl(origin: string): string {
  return `${origin}/`;
}

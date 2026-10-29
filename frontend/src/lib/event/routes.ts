export const ROUTES = {
  info: "/",
  stamp: "/stempelkarte",
  withdraw: "/raffle/withdraw",
  services: "/services",
  redeem: (code: string) => `/redeem?code=${encodeURIComponent(code)}`,
} as const;

export function stationQrUrl(origin: string, stationId: string): string {
  return `${origin}${ROUTES.stamp}?stand=${encodeURIComponent(stationId)}`;
}

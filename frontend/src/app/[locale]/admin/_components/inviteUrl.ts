/** The address of an invitation, without a locale prefix. */
export function inviteUrl(origin: string, token: string): string {
  return `${origin.replace(/\/+$/, "")}/einladung/${token}`;
}

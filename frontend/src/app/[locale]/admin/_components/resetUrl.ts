/** The address of a password reset link, without a locale prefix. */
export function resetUrl(origin: string, token: string): string {
  return `${origin.replace(/\/+$/, "")}/reset-password/${token}`;
}

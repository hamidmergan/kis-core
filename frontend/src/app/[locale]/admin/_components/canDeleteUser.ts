/** Who is offered a delete button in the user list. */

type Zeile = { id: number; email?: string | null };
type Angemeldet = { userId: number; email: string };

/** Your own and the configuration account stay without a button. */
export function canDeleteUser(zeile: Zeile, ich: Angemeldet): boolean {
  if (zeile.id === ich.userId) return false;
  const mail = (zeile.email || "").toLowerCase();
  return !(mail && mail === ich.email.toLowerCase());
}

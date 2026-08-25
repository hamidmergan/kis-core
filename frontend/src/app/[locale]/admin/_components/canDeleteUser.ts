/**
 * Wem in der Nutzerliste ein Papierkorb angeboten wird.
 *
 * Eigene Datei neben der Komponente, wie ``renameCommit``: die Entscheidung ist
 * pruefbare Logik, die Zeile drumherum ist nur Darstellung.
 */

type Zeile = { id: number; email?: string | null };
type Angemeldet = { userId: number; email: string };

/**
 * Das eigene Konto und das Konto aus der Konfiguration bleiben ohne Knopf.
 *
 * Die Mailadresse ist derselbe Vergleich, mit dem die Rollenspalte schon heute
 * das geschuetzte Konto erkennt. Das Backend sperrt beides ohnehin, hier geht
 * es nur darum, einen Knopf zu vermeiden, der immer scheitert.
 */
export function canDeleteUser(zeile: Zeile, ich: Angemeldet): boolean {
  if (zeile.id === ich.userId) return false;
  const mail = (zeile.email || "").toLowerCase();
  return !(mail && mail === ich.email.toLowerCase());
}

"use client";

/**
 * Die Seite Nutzer > Rollen zeigt die Rechtetabelle.
 *
 * Vorher standen hier eine Liste eigener Rollen und ein Dialog dahinter. Die
 * Liste konnte nur zwei Dinge: Zugriff auf den KI-Assistenten und ein paar
 * Werkzeuge. Alles, was den Bereich selbst betrifft, war gar nicht vergebbar.
 */

import PermissionMatrix from "./PermissionMatrix";

export default function RolesTab() {
  return <PermissionMatrix />;
}

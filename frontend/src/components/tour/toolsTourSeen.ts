/**
 * Whether someone already went through the tour of the tools.
 *
 * Its own mark next to the one for the course tour: two invitations, and
 * waving one away must not silence the other. Like the first it sits on the
 * account, so a second device does not start the invitation all over again.
 */

export async function ladeWerkzeugTourGesehen(): Promise<boolean> {
  try {
    const res = await fetch("/api/me", { credentials: "include" });
    if (!res.ok) return true; // Im Zweifel nicht einladen, das ist die leisere Störung.
    const daten = await res.json();
    return daten.tools_tour_seen_at !== null && daten.tools_tour_seen_at !== undefined;
  } catch {
    return true;
  }
}

export async function merkeWerkzeugTourGesehen(seen: boolean): Promise<void> {
  try {
    await fetch("/api/me/tools-tour-seen", {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ seen }),
    });
  } catch {
    /* Der Rundgang lief trotzdem, das Merken ist die Zugabe. */
  }
}

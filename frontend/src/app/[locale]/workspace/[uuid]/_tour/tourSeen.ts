/**
 * Whether someone already went through the tour.
 *
 * Sits on the account, not in the browser: otherwise a second device or a
 * cleared cache starts the invitation all over again, and whoever went through
 * it on the laptop gets asked again on the tablet.
 */

export async function ladeTourGesehen(): Promise<boolean> {
  try {
    const res = await fetch("/api/me", { credentials: "include" });
    if (!res.ok) return true; // When in doubt do not invite, the quieter disruption.
    const daten = await res.json();
    return daten.tour_seen_at !== null && daten.tour_seen_at !== undefined;
  } catch {
    return true;
  }
}

export async function merkeTourGesehen(seen: boolean): Promise<void> {
  try {
    await fetch("/api/me/tour-seen", {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ seen }),
    });
  } catch {
    /* The tour ran anyway, remembering it is the extra. */
  }
}

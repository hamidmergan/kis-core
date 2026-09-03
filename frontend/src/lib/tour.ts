/**
 * Starting the tour from anywhere in the app.
 *
 * The tour itself runs inside a course, its steps point at the sources list,
 * the chat and the studio. Whoever starts it from the header is therefore not
 * in the right place yet: this looks for the demo course, joins it in the
 * background if needed, and hands back the target address.
 */

interface DemoKurs {
  uuid: string;
  joined: boolean;
  owned: boolean;
}

/** The demo course someone may be guided through, or null if there is none. */
export async function findeRundgangKurs(): Promise<DemoKurs | null> {
  try {
    const res = await fetch("/api/ai-assistant/demo/workspaces", { credentials: "include" });
    if (!res.ok) return null;
    const kurse: DemoKurs[] = await res.json();
    // Den eigenen Kurs als Demo anzubieten waere sinnlos, da ist man schon drin.
    return kurse.find((k) => !k.owned) ?? null;
  } catch {
    return null;
  }
}

/** Joins if needed and returns the path the tour starts on. */
export async function rundgangZiel(kurs: DemoKurs): Promise<string> {
  if (!kurs.joined) {
    try {
      await fetch("/api/ai-assistant/demo/enroll", {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ workspace_uuid: kurs.uuid }),
      });
    } catch {
      /* Ohne Beitritt landet man auf der Sperrseite, das sagt mehr als ein stiller Abbruch. */
    }
  }
  return `/workspace/${kurs.uuid}?tour=1`;
}

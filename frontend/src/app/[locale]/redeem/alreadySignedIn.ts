/** Whether the browser already holds a live session, then a code link must not create a second account. */
export async function alreadySignedIn(): Promise<boolean> {
  try {
    const r = await fetch("/api/me", { credentials: "include", cache: "no-store" });
    return r.ok;
  } catch {
    return false;
  }
}

/** Codes are stored lowercase and looked up exactly, so anything else has to be normalised first. */
const CODE = /^[a-z0-9]{4,64}$/;

/** Pulls the bare access code out of whatever someone pasted into the join field. */
export function extractJoinCode(raw: string): string | null {
  // A pasted link carries the code in its query, everything else is noise.
  const fromLink = raw.match(/[?&]code=([^&\s#]+)/i);
  const candidate = (fromLink ? fromLink[1] : raw).replace(/\s+/g, "").toLowerCase();
  return CODE.test(candidate) ? candidate : null;
}

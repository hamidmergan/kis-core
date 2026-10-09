import type { Source } from "../_types";

// Sends media in parts straight into the bucket, null means the classic upload fits better.

interface Session {
  direct: boolean;
  token: string;
  part_size: number;
  part_count: number;
  uploaded: number[];
}

type HttpError = Error & { status?: number };

const URL_BATCH = 10;
const MAX_TRIES = 8;

function storageKey(uuid: string, file: File): string {
  return `kis-direct-upload:${uuid}:${file.name}:${file.size}:${file.lastModified}`;
}

function readToken(key: string): string | null {
  try { return localStorage.getItem(key); } catch { return null; }
}

function writeToken(key: string, token: string | null): void {
  try {
    if (token) localStorage.setItem(key, token);
    else localStorage.removeItem(key);
  } catch { /* the upload works without resuming too */ }
}

async function httpError(res: Response, fallback: string): Promise<HttpError> {
  let detail = fallback;
  try {
    const body = await res.json();
    // The reason arrives sometimes as an object and sometimes as text.
    if (typeof body?.detail === "string") detail = body.detail;
    else if (body?.detail?.message) detail = body.detail.message;
  } catch { /* keep the fallback */ }
  return Object.assign(new Error(detail), { status: res.status });
}

function sleep(ms: number): Promise<void> {
  return new Promise((r) => setTimeout(r, ms));
}

// Waits until the device is online again, a dropped line should not cost the upload.
function whenOnline(): Promise<void> {
  if (typeof navigator === "undefined" || navigator.onLine) return Promise.resolve();
  return new Promise((r) => window.addEventListener("online", () => r(), { once: true }));
}

// Without cookies the browser opens a connection of its own, the page's requests never queue behind a part.
async function putPart(url: string, blob: Blob): Promise<void> {
  let res: Response;
  try {
    res = await fetch(url, { method: "PUT", body: blob, credentials: "omit" });
  } catch {
    throw Object.assign(new Error("network"), { status: 0 });
  }
  if (!res.ok) throw Object.assign(new Error(`part ${res.status}`), { status: res.status });
}

export async function directUpload(
  uuid: string,
  file: File,
  onPercent: (percent: number) => void,
  failedText: string,
): Promise<Source | null> {
  const base = `/api/ai-assistant/workspaces/${uuid}/direct-uploads`;
  const key = storageKey(uuid, file);

  let session: Session | null = null;
  const saved = readToken(key);
  if (saved) {
    const res = await fetch(`${base}/${saved}`, { credentials: "include" });
    if (res.ok) session = await res.json();
    else writeToken(key, null);
  }
  if (!session) {
    const res = await fetch(base, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ filename: file.name, size: file.size }),
    });
    if (!res.ok) throw await httpError(res, failedText);
    session = await res.json();
    if (!session?.direct) return null;
    writeToken(key, session.token);
  }

  const { token, part_size: partSize, part_count: partCount } = session;
  const done = new Set(session.uploaded);
  const partBytes = (n: number) => Math.min(partSize, file.size - (n - 1) * partSize);
  let doneBytes = [...done].reduce((sum, n) => sum + partBytes(n), 0);
  const report = () => onPercent(Math.min(99, Math.floor((doneBytes / file.size) * 100)));
  report();

  const todo = Array.from({ length: partCount }, (_, i) => i + 1).filter((n) => !done.has(n));
  let anyPartSent = done.size > 0;
  // One part at a time, the line stays usable for the page and nothing runs in parallel.
  for (let i = 0; i < todo.length; i += URL_BATCH) {
    const batch = todo.slice(i, i + URL_BATCH);
    const urlRes = await fetch(`${base}/${token}/urls`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ parts: batch }),
    });
    if (!urlRes.ok) throw await httpError(urlRes, failedText);
    const { urls } = (await urlRes.json()) as { urls: Record<string, string> };

    for (const n of batch) {
      const blob = file.slice((n - 1) * partSize, (n - 1) * partSize + partBytes(n));
      for (let attempt = 1; ; attempt++) {
        try {
          await whenOnline();
          await putPart(urls[String(n)], blob);
          break;
        } catch (err) {
          const status = (err as HttpError).status ?? 0;
          // The bucket refuses the browser outright, the classic route still works then.
          if (!anyPartSent && status === 0 && attempt === 1) {
            await fetch(`${base}/${token}`, { method: "DELETE", credentials: "include" }).catch(() => {});
            writeToken(key, null);
            return null;
          }
          if (attempt >= MAX_TRIES) throw Object.assign(new Error(failedText), { status });
          await sleep(Math.min(30_000, 1000 * 2 ** (attempt - 1)));
        }
      }
      anyPartSent = true;
      doneBytes += partBytes(n);
      report();
    }
  }

  const res = await fetch(`${base}/${token}/complete`, { method: "POST", credentials: "include" });
  if (!res.ok) {
    // Parts that never arrived are sent again on the next try, everything else starts over.
    if (res.status !== 409) writeToken(key, null);
    throw await httpError(res, failedText);
  }
  writeToken(key, null);
  onPercent(100);
  return (await res.json()) as Source;
}

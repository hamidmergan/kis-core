// Reads and formats WebVTT, without React and therefore testable on its own.

export interface Cue {
  start: number;
  end: number;
  text: string;
}

function parseTs(s: string): number {
  const parts = s.split(":");
  if (parts.length < 2) return NaN;
  const sec = parts[parts.length - 1].replace(",", ".");
  const m = parseInt(parts[parts.length - 2] || "0", 10);
  const h = parts.length >= 3 ? parseInt(parts[0], 10) : 0;
  return h * 3600 + m * 60 + parseFloat(sec);
}

/** The cues of a VTT file, a cue without text or with a broken time is skipped. */
export function parseVtt(raw: string): Cue[] {
  const cues: Cue[] = [];
  const lines = raw.replace(/\r/g, "").split("\n");
  let i = 0;
  while (i < lines.length) {
    const line = lines[i].trim();
    const arrow = line.indexOf("-->");
    if (arrow === -1) { i++; continue; }
    const start = parseTs(line.slice(0, arrow).trim());
    const end = parseTs(line.slice(arrow + 3).trim().split(" ")[0]);
    i++;
    const textLines: string[] = [];
    while (i < lines.length && lines[i].trim() !== "") {
      textLines.push(lines[i]);
      i++;
    }
    if (!Number.isNaN(start) && !Number.isNaN(end) && textLines.length) {
      cues.push({ start, end, text: textLines.join(" ").trim() });
    }
    i++;
  }
  return cues;
}

/** Seconds as mm:ss, with the hours in front once there are any. */
export function fmtTs(sec: number): string {
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  const s = Math.floor(sec % 60);
  const mm = String(m).padStart(2, "0");
  const ss = String(s).padStart(2, "0");
  return h > 0 ? `${h}:${mm}:${ss}` : `${mm}:${ss}`;
}

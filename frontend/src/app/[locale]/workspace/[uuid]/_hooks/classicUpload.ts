import { parseDetail } from "@/lib/api";
import type { Source } from "../_types";

/** Sends one file through the backend in a single request, a failure carries the HTTP status. */
export function classicUpload(
  uuid: string,
  file: File,
  onPercent: (percent: number) => void,
  texts: { failed: string; network: string },
): Promise<Source> {
  return new Promise<Source>((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `/api/ai-assistant/workspaces/${uuid}/sources`);
    xhr.withCredentials = true;
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) onPercent(Math.round((e.loaded / e.total) * 100));
    };
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(JSON.parse(xhr.responseText) as Source);
        return;
      }
      let detail = texts.failed;
      try {
        detail = parseDetail(JSON.parse(xhr.responseText)?.detail, texts.failed);
      } catch { /* keep the fallback */ }
      reject(Object.assign(new Error(detail), { status: xhr.status }));
    };
    xhr.onerror = () => reject(new Error(texts.network));
    const form = new FormData();
    form.append("file", file);
    xhr.send(form);
  });
}

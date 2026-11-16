/** Starts a download through a link that never sits in the page, so the top loader stays quiet. */
export function triggerUrlDownload(href: string, filename = ""): void {
  const a = document.createElement("a");
  a.href = href;
  a.download = filename;
  a.click();
}

/** Saves a blob the page already holds under the given file name. */
export function triggerBlobDownload(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

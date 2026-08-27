// Copies asynchronously fetched text, the promise holds the gesture on iOS Safari.
export function copyTextFromPromise(textPromise: Promise<string>): void {
  if (window.isSecureContext && navigator.clipboard?.write && typeof ClipboardItem !== "undefined") {
    const blob = textPromise.then((t) => new Blob([t], { type: "text/plain" }));
    navigator.clipboard.write([new ClipboardItem({ "text/plain": blob })])
      .catch(() => { textPromise.then(execCommandCopy).catch(() => { /* ignore */ }); });
    return;
  }
  textPromise.then(execCommandCopy).catch(() => { /* ignore */ });
}

function execCommandCopy(text: string) {
  if (!text) return;
  const ta = document.createElement("textarea");
  ta.value = text;
  ta.setAttribute("readonly", "");
  ta.style.position = "fixed";
  ta.style.opacity = "0";
  document.body.appendChild(ta);
  ta.select();
  document.execCommand("copy");
  document.body.removeChild(ta);
}

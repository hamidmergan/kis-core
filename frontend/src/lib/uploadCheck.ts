type UploadProblem = "extension" | "size";

// Returns the first reason a picked file cannot be uploaded, or null.
export function checkUpload(
  file: { name: string; size: number },
  extensions: readonly string[],
  maxBytes: number,
): UploadProblem | null {
  const ext = "." + file.name.split(".").pop()?.toLowerCase();
  if (!extensions.includes(ext)) return "extension";
  if (file.size > maxBytes) return "size";
  return null;
}

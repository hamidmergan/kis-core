import { MAX_IMAGE_BYTES } from "@/lib/constants";

export const SIZES = ["1024x1024", "1280x720"] as const;
export const COUNTS = [1, 2, 3, 4] as const;
export const ALLOWED_EXTS = new Set([".png", ".jpg", ".jpeg"]);

export function validateImageFile(file: File): string | null {
  const ext = "." + file.name.split(".").pop()?.toLowerCase();
  if (!ALLOWED_EXTS.has(ext)) return "Nur PNG oder JPG erlaubt";
  if (file.size > MAX_IMAGE_BYTES) return "Bild zu groß (max 20 MB)";
  return null;
}

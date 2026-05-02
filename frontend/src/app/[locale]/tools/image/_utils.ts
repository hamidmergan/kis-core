import { MAX_IMAGE_BYTES } from "@/lib/constants";

export const SIZES = ["1024x1024", "1280x720"] as const;
export const COUNTS = [1, 2, 3, 4] as const;
export const ALLOWED_EXTS = new Set([".png", ".jpg", ".jpeg"]);

type CommonT = (key: string, params?: Record<string, unknown>) => string;

export function validateImageFile(file: File, t: CommonT): string | null {
  const ext = "." + file.name.split(".").pop()?.toLowerCase();
  if (!ALLOWED_EXTS.has(ext)) return t("onlyExtsAllowed", { exts: "PNG, JPG" });
  if (file.size > MAX_IMAGE_BYTES) return t("fileTooLarge", { n: 20 });
  return null;
}

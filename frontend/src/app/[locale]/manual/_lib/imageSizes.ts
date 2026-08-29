import fs from "node:fs";
import path from "node:path";

export type ImageSize = { width: number; height: number };

const PUBLIC_ROOT = path.join(process.cwd(), "public");
/** manual-images.spec.ts shoots at twice the pixels, so half of them is the display size. */
const SHOT_SCALE = 2;

/** Reads width and height out of the PNG header, no image library needed. */
export function pngSize(file: string): ImageSize | null {
  let handle: number | null = null;
  try {
    handle = fs.openSync(file, "r");
    const header = Buffer.alloc(24);
    if (fs.readSync(handle, header, 0, 24, 0) < 24) return null;
    if (header.toString("ascii", 1, 4) !== "PNG") return null;
    return { width: header.readUInt32BE(16), height: header.readUInt32BE(20) };
  } catch {
    return null;
  } finally {
    if (handle !== null) fs.closeSync(handle);
  }
}

/** Collects the display size of every image the markdown points at under /public. */
export function imageSizes(markdown: string, root: string = PUBLIC_ROOT): Record<string, ImageSize> {
  const sizes: Record<string, ImageSize> = {};
  for (const match of markdown.matchAll(/!\[[^\]]*\]\((\/[^)\s]+\.png)\)/g)) {
    const src = match[1];
    if (sizes[src]) continue;
    const size = pngSize(path.join(root, src));
    if (size) sizes[src] = { width: Math.round(size.width / SHOT_SCALE), height: Math.round(size.height / SHOT_SCALE) };
  }
  return sizes;
}

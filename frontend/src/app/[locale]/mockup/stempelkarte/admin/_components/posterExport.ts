import { triggerBlobDownload } from "../../../../tools/screencast/_utils";

/** A5 in millimetres, the SVG viewBox uses the same units. */
export const POSTER_MM = { w: 148, h: 210 } as const;
const PX_PER_MM = 8;

function loadImage(src: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = () => reject(new Error("poster image failed"));
    img.src = src;
  });
}

/** Serialises the poster SVG, paints it on a canvas and downloads the PNG. */
export async function exportPosterPng(svg: SVGSVGElement, filename: string): Promise<void> {
  const w = POSTER_MM.w * PX_PER_MM;
  const h = POSTER_MM.h * PX_PER_MM;
  const clone = svg.cloneNode(true) as SVGSVGElement;
  clone.setAttribute("xmlns", "http://www.w3.org/2000/svg");
  clone.setAttribute("width", String(w));
  clone.setAttribute("height", String(h));
  clone.removeAttribute("class");
  clone.removeAttribute("style");
  const xml = new XMLSerializer().serializeToString(clone);
  const src = URL.createObjectURL(new Blob([xml], { type: "image/svg+xml;charset=utf-8" }));
  try {
    const img = await loadImage(src);
    const canvas = document.createElement("canvas");
    canvas.width = w;
    canvas.height = h;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.fillStyle = "#ffffff";
    ctx.fillRect(0, 0, w, h);
    ctx.drawImage(img, 0, 0, w, h);
    const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, "image/png"));
    if (blob) triggerBlobDownload(blob, filename);
  } finally {
    URL.revokeObjectURL(src);
  }
}

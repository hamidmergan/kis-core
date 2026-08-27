import { test, expect, Page } from "@playwright/test";

/** The length check on upload, with a test file created in the browser. */

const MINUTES_LIMIT = 100;

/** Build a silent WAV of `seconds` length and hand it to the file input. */
async function selectGeneratedAudio(page: Page, seconds: number, filename: string) {
  await page.evaluate(
    ({ seconds, filename }) => {
      const sampleRate = 8000;
      const dataLen = sampleRate * seconds; // 8-bit mono => 1 byte per sample
      const buf = new ArrayBuffer(44 + dataLen);
      const view = new DataView(buf);
      const ascii = (offset: number, s: string) => {
        for (let i = 0; i < s.length; i++) view.setUint8(offset + i, s.charCodeAt(i));
      };
      ascii(0, "RIFF");
      view.setUint32(4, 36 + dataLen, true);
      ascii(8, "WAVE");
      ascii(12, "fmt ");
      view.setUint32(16, 16, true);
      view.setUint16(20, 1, true); // PCM
      view.setUint16(22, 1, true); // mono
      view.setUint32(24, sampleRate, true);
      view.setUint32(28, sampleRate, true);
      view.setUint16(32, 1, true);
      view.setUint16(34, 8, true);
      ascii(36, "data");
      view.setUint32(40, dataLen, true);
      new Uint8Array(buf, 44).fill(128); // silence, unsigned 8-bit midpoint

      const file = new File([buf], filename, { type: "audio/wav" });
      const dt = new DataTransfer();
      dt.items.add(file);
      const input = document.querySelector('input[type="file"]') as HTMLInputElement;
      input.files = dt.files;
      input.dispatchEvent(new Event("change", { bubbles: true }));
    },
    { seconds, filename },
  );
}

test.beforeEach(async ({ page }) => {
  await page.goto("/de/tools/stt", { waitUntil: "domcontentloaded" });
  await expect(page.getByRole("heading", { name: "Sprache in Text" })).toBeVisible();
});

test("a recording over the limit is refused without uploading it", async ({ page }) => {
  let uploads = 0;
  page.on("request", (r) => {
    if (r.method() === "POST" && r.url().includes("/transcription")) uploads++;
  });

  await selectGeneratedAudio(page, (MINUTES_LIMIT + 2) * 60, "zu-lang.wav");

  await expect(page.getByText(/Aufnahme zu lang/)).toBeVisible();
  await expect(page.getByText(new RegExp(`${MINUTES_LIMIT} Minuten`))).toBeVisible();
  // The point of the guard: the body never leaves the browser.
  expect(uploads).toBe(0);
});

test("a recording under the limit is accepted", async ({ page }) => {
  await selectGeneratedAudio(page, 5 * 60, "kurz.wav");

  await expect(page.getByText("kurz.wav")).toBeVisible();
  await expect(page.getByText(/Aufnahme zu lang/)).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Transkription starten" })).toBeEnabled();
});

test("a recording exactly at the limit is accepted", async ({ page }) => {
  // If the browser rounded the other way it would block valid files.
  await selectGeneratedAudio(page, MINUTES_LIMIT * 60, "genau-100.wav");

  await expect(page.getByText("genau-100.wav")).toBeVisible();
  await expect(page.getByText(/Aufnahme zu lang/)).toHaveCount(0);
});

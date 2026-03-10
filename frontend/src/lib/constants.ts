/** Max upload size for general documents (translate, summary, image). */
export const MAX_UPLOAD_MB = 200;
export const MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024;

/** Max upload size for audio/video transcription. */
export const MAX_TRANSCRIPTION_MB = 200;
export const MAX_TRANSCRIPTION_BYTES = MAX_TRANSCRIPTION_MB * 1024 * 1024;

/** Max upload size for images (image edit/analyze). */
export const MAX_IMAGE_MB = 10;
export const MAX_IMAGE_BYTES = MAX_IMAGE_MB * 1024 * 1024;

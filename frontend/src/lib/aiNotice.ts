import { AI_HINWEIS_TEXT } from "@/lib/constants";

const VTT_NOTICE_MARKER = `NOTE ${AI_HINWEIS_TEXT}\n\n`;
const VTT_HEADER_SEPARATOR = /\r?\n\r?\n/;

/** Plain text with the notice as a leading line, mirrors the backend's text_with_notice(). */
export function withAiNoticeText(text: string): string {
  return `${AI_HINWEIS_TEXT}\n\n${text}`;
}

/** Removes a leading notice line added by withAiNoticeText(), if present. */
export function stripAiNoticeText(text: string): string {
  const prefix = `${AI_HINWEIS_TEXT}\n\n`;
  return text.startsWith(prefix) ? text.slice(prefix.length) : text;
}

/** A WebVTT file with the notice as a NOTE line after the header, mirrors the backend's vtt_with_notice(). */
export function withAiNoticeVtt(vttText: string): string {
  const match = VTT_HEADER_SEPARATOR.exec(vttText);
  if (!vttText.startsWith("WEBVTT") || !match) return vttText;
  const end = match.index + match[0].length;
  return `${vttText.slice(0, end)}${VTT_NOTICE_MARKER}${vttText.slice(end)}`;
}

/** Removes a NOTE line added by withAiNoticeVtt(), if present. */
export function stripAiNoticeVtt(vttText: string): string {
  return vttText.includes(VTT_NOTICE_MARKER) ? vttText.replace(VTT_NOTICE_MARKER, "") : vttText;
}

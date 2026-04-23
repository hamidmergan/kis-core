const WORDS_PER_MINUTE = 150;

export function wordCount(text: string): number {
  return text.split(/\s+/).filter(Boolean).length;
}

export function estimateDuration(words: number): number {
  return Math.round((words / WORDS_PER_MINUTE) * 60);
}

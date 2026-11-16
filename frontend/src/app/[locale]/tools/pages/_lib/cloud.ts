/** The words of a cloud, the heaviest first, each with its letter size between 16 and 66. */
export function sizedWords(words: [string, number][]): { word: string; size: number }[] {
  const sorted = [...words].sort((a, b) => b[1] - a[1]);
  const weights = sorted.map(([, n]) => n);
  const max = Math.max(...weights), min = Math.min(...weights);
  return sorted.map(([word, n]) => ({ word, size: 16 + Math.sqrt((n - min) / (max - min || 1)) * 50 }));
}

/** Shuffles the options, except for true/false where the order matters. */

type WithOptions = { options?: string[]; correct_idx?: number };

export function shuffleOptions<T extends WithOptions>(item: T): T {
  const options = item.options;
  if (!options || item.correct_idx === undefined || options.length < 3) return item;
  const indices = options.map((_, i) => i);
  for (let i = indices.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [indices[i], indices[j]] = [indices[j], indices[i]];
  }
  return {
    ...item,
    options: indices.map((i) => options[i]),
    correct_idx: indices.indexOf(item.correct_idx),
  };
}

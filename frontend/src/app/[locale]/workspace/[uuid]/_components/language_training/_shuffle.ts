/** Shuffling for the exercise views: a whole list, and the options of one item. */

type WithOptions = { options?: string[]; correct_idx?: number };

/** A shuffled copy, the list itself stays as it is. */
export function shuffled<T>(list: readonly T[]): T[] {
  const out = [...list];
  for (let i = out.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [out[i], out[j]] = [out[j], out[i]];
  }
  return out;
}

/** Shuffles the options, except for true/false where the order matters. */
export function shuffleOptions<T extends WithOptions>(item: T): T {
  const options = item.options;
  if (!options || item.correct_idx === undefined || options.length < 3) return item;
  const indices = shuffled(options.map((_, i) => i));
  return {
    ...item,
    options: indices.map((i) => options[i]),
    correct_idx: indices.indexOf(item.correct_idx),
  };
}

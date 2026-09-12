/** Which demo module the guided tour runs in. */

interface Waehlbar {
  /** The viewer owns it, then there is nothing to be guided through. */
  owned: boolean;
  /** Marked as the tour module by its owner. */
  tour?: boolean;
}

/**
 * The marked module, otherwise the first foreign one.
 *
 * The tour's stations point at the demo files by name, so with more than one
 * demo module the first one in the list is a coin toss. The fallback keeps an
 * installation without any mark working exactly as before.
 */
export function waehleRundgangModul<T extends Waehlbar>(module: readonly T[]): T | undefined {
  const fremde = module.filter((m) => !m.owned);
  return fremde.find((m) => m.tour) ?? fremde[0];
}

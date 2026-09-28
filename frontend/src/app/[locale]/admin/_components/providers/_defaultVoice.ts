import type { Provider } from "./_types";

export type VoiceOption = { value: string; label: string };

/** The voices of the starred provider, all voices while no listed provider carries the star. */
export function defaultVoiceOptions(eligible: Provider[], starId: number | null): VoiceOption[] {
  const starred = eligible.filter((p) => p.id === starId);
  if (starred.length) {
    return starred.flatMap((p) => (p.voices ?? []).map((v) => ({ value: `${p.id}:${v.voice_id}`, label: v.name })));
  }
  return eligible.flatMap((p) =>
    (p.voices ?? []).map((v) => ({ value: `${p.id}:${v.voice_id}`, label: `${p.name} · ${v.name}` })),
  );
}

/** What the field shows, a stored voice of another provider than the starred one counts as not chosen. */
export function shownDefaultVoice(
  options: VoiceOption[],
  stored: string,
  starId: number | null,
): { shown: string; orphaned: boolean } {
  const first = options[0]?.value ?? "";
  if (!stored) return { shown: first, orphaned: false };
  if (options.some((o) => o.value === stored)) return { shown: stored, orphaned: false };
  // Split at the first colon, the voice id may carry one itself.
  const storedProvider = Number(stored.slice(0, stored.indexOf(":")));
  const starOnly = starId != null && options.length > 0 && options.every((o) => o.value.startsWith(`${starId}:`));
  return { shown: first, orphaned: !(starOnly && storedProvider !== starId) };
}

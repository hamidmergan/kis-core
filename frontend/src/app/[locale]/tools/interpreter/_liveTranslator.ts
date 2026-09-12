/** Translates the text somebody is still producing: one request in flight, one every gap, always the newest text. */

export interface LiveTranslator {
  schedule: (text: string) => void;
  cancel: () => void;
}

export function createLiveTranslator<R = string>(
  run: (text: string) => Promise<R>,
  onResult: (text: string, result: R) => void,
  minGapMs = 1200,
): LiveTranslator {
  let inFlight = false;
  let lastSentAt = 0;
  let pending: string | null = null;
  let timer: ReturnType<typeof setTimeout> | null = null;
  // A cancel invalidates every answer still on its way.
  let generation = 0;

  const fire = async (text: string) => {
    const mine = generation;
    inFlight = true;
    lastSentAt = Date.now();
    try {
      const result = await run(text);
      if (mine === generation) onResult(text, result);
    } catch {
      // The final translation after the turn ends tries again.
    } finally {
      inFlight = false;
      const next = pending;
      pending = null;
      if (next !== null && next !== text && mine === generation) schedule(next);
    }
  };

  const schedule = (text: string) => {
    if (!text.trim()) return;
    if (inFlight) {
      pending = text;
      return;
    }
    const wait = Math.max(0, minGapMs - (Date.now() - lastSentAt));
    if (timer) clearTimeout(timer);
    if (wait === 0) {
      void fire(text);
      return;
    }
    pending = text;
    timer = setTimeout(() => {
      timer = null;
      const next = pending ?? text;
      pending = null;
      void fire(next);
    }, wait);
  };

  const cancel = () => {
    generation += 1;
    if (timer) clearTimeout(timer);
    timer = null;
    pending = null;
  };

  return { schedule, cancel };
}

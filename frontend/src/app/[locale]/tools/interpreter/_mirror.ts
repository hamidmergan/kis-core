import type { Turn } from "./_types";

/** Carries every change of a sentence to the server: one request per sentence at a time, the newest version wins. */
export interface Mirror {
  push: (turn: Turn) => void;
  /** Sends everything that still waits and resolves once the server has it. */
  flush: () => Promise<void>;
  /** Drops everything that still waits, answers on their way are left alone. */
  cancel: () => void;
}

export function createMirror(put: (turn: Turn) => Promise<unknown>, minGapMs = 1000): Mirror {
  const waiting = new Map<string, Turn>();
  const timers = new Map<string, ReturnType<typeof setTimeout>>();
  const inFlight = new Map<string, Promise<void>>();
  let generation = 0;

  const send = (id: string) => {
    const turn = waiting.get(id);
    if (!turn || inFlight.has(id)) return;
    waiting.delete(id);
    const mine = generation;
    const job = put(turn)
      .catch(() => {
        // The next change of this sentence carries it again.
      })
      .then(() => {
        inFlight.delete(id);
        if (mine !== generation) return;
        timers.set(id, setTimeout(() => {
          timers.delete(id);
          send(id);
        }, minGapMs));
      });
    inFlight.set(id, job);
  };

  const push = (turn: Turn) => {
    waiting.set(turn.id, turn);
    if (!timers.has(turn.id)) send(turn.id);
  };

  const flush = async () => {
    for (;;) {
      for (const [id, timer] of timers) {
        clearTimeout(timer);
        timers.delete(id);
      }
      for (const id of [...waiting.keys()]) send(id);
      if (inFlight.size === 0) return;
      await Promise.all([...inFlight.values()]);
    }
  };

  const cancel = () => {
    generation += 1;
    for (const timer of timers.values()) clearTimeout(timer);
    timers.clear();
    waiting.clear();
  };

  return { push, flush, cancel };
}

"use client";

/**
 * Listens to the loudness of the microphone, so a window without a voice never reaches Whisper.
 * The threshold sits low on purpose: only real silence counts as silence, a quiet speaker still
 * passes. Whisper invents sentences on silence, that is what this keeps away.
 */

/** Loudness below this counts as silence, roughly a quiet room. */
export const SPEECH_LEVEL = 0.008;

export interface VoiceTracker {
  /** One loudness reading between 0 and 1. */
  sample: (level: number) => void;
  /** Was there a voice since the last time this was asked? Asking resets it. */
  takeHeard: () => boolean;
  /** Did this recording ever hear a voice? */
  everHeard: () => boolean;
  /** Milliseconds since the last voice, counted from the start when there was none. */
  quietMs: () => number;
}

export function createVoiceTracker(now: () => number = Date.now): VoiceTracker {
  let lastVoiceAt = now();
  let heard = false;
  let ever = false;
  return {
    sample: (level) => {
      if (level < SPEECH_LEVEL) return;
      lastVoiceAt = now();
      heard = true;
      ever = true;
    },
    takeHeard: () => {
      const was = heard;
      heard = false;
      return was;
    },
    everHeard: () => ever,
    quietMs: () => now() - lastVoiceAt,
  };
}

export interface VoiceMeter extends VoiceTracker {
  close: () => void;
}

const SAMPLE_MS = 100;

/** The loudness of a live microphone, read a few times a second. */
export function createVoiceMeter(stream: MediaStream): VoiceMeter | null {
  const Ctor = typeof window === "undefined"
    ? undefined
    : window.AudioContext ?? (window as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
  if (!Ctor) return null;
  let context: AudioContext;
  try {
    context = new Ctor();
  } catch {
    return null;
  }
  const analyser = context.createAnalyser();
  analyser.fftSize = 1024;
  const source = context.createMediaStreamSource(stream);
  source.connect(analyser);
  const buffer = new Float32Array(analyser.fftSize);
  const tracker = createVoiceTracker();

  const timer = setInterval(() => {
    analyser.getFloatTimeDomainData(buffer);
    let sum = 0;
    for (const value of buffer) sum += value * value;
    tracker.sample(Math.sqrt(sum / buffer.length));
  }, SAMPLE_MS);

  return {
    ...tracker,
    close: () => {
      clearInterval(timer);
      source.disconnect();
      void context.close().catch(() => {});
    },
  };
}

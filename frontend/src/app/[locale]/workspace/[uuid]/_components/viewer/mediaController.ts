/** What the transcript needs from a player, whatever plays the video. */
export interface MediaController {
  currentTime(): number;
  seek(seconds: number): void;
  play(): void;
  /** Calls the listener whenever the time moves and returns the unsubscribe. */
  onTime(listener: () => void): () => void;
}

/** The controller for a plain video or audio element. */
export function htmlMediaController(el: HTMLMediaElement): MediaController {
  return {
    currentTime: () => el.currentTime,
    seek: (seconds) => { el.currentTime = seconds; },
    play: () => { el.play().catch(() => { }); },
    onTime: (listener) => {
      el.addEventListener("timeupdate", listener);
      return () => el.removeEventListener("timeupdate", listener);
    },
  };
}

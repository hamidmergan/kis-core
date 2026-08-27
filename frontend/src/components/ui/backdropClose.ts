import type { MouseEvent } from "react";

/** A click outside closes, selecting in a field does not, so the click start counts too. */

export type BackdropPress = { startedOnBackdrop: boolean };

/** The marker for one dialog, it belongs in a ``useRef`` and has to survive redraws. */
export function newBackdropPress(): BackdropPress {
  return { startedOnBackdrop: false };
}

/** The two handlers, 'enabled' false means it does not close right now. */
export function backdropClose(
  press: BackdropPress,
  onClose: () => void,
  enabled = true,
) {
  return {
    onMouseDown: (e: MouseEvent) => {
      press.startedOnBackdrop = e.target === e.currentTarget;
    },
    onClick: (e: MouseEvent) => {
      if (enabled && press.startedOnBackdrop && e.target === e.currentTarget) onClose();
    },
  };
}

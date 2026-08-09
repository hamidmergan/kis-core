import type { MouseEvent } from "react";

/**
 * Klick daneben schliesst das Fenster, Markieren im Feld aber nicht.
 *
 * Der Browser feuert `click` nicht dort, wo die Maus losgelassen wird, sondern auf dem
 * gemeinsamen Elternteil von Druck und Loslassen. Wer in einem Eingabefeld markiert und
 * die Taste ueber dem Hintergrund loslaesst, erzeugt also einen Klick auf dem
 * Hintergrund, und ein blosses `onClick={onClose}` haelt das faelschlich fuer "daneben
 * geklickt". Ein `stopPropagation` im Inhalt hilft dagegen nicht, das Ereignis entsteht
 * schon oben.
 *
 * Deshalb zaehlt hier nicht nur, wo der Klick endet, sondern auch, wo er begonnen hat.
 */

export type BackdropPress = { startedOnBackdrop: boolean };

/** Der Merker fuer ein Fenster. Gehoert in ein ``useRef``, er muss Neuzeichnen ueberleben. */
export function newBackdropPress(): BackdropPress {
  return { startedOnBackdrop: false };
}

/**
 * Die beiden Behandler fuer den Hintergrund.
 *
 * ``enabled`` auf ``false`` heisst: der Hintergrund schliesst gerade nicht, etwa waehrend
 * gespeichert wird.
 */
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

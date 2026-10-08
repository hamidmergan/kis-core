"use client";

import type { SlideData } from "@/types";
import Lightbox from "./Lightbox";
import ExitConfirmModal from "./ExitConfirmModal";

interface Props {
  slides: SlideData[];
  pendingExit: "restart" | "cancel" | "render" | null;
  onExitCancel: () => void;
  onExitConfirm: () => void;
  lightboxIndex: number | null;
  onLightboxIndexChange: (index: number | null) => void;
}

/** The two windows that lie over the steps: exit prompt and image view. */
export default function ScreencastOverlays({
  slides, pendingExit, onExitCancel, onExitConfirm,
  lightboxIndex, onLightboxIndexChange,
}: Props) {
  return (
    <>
      {pendingExit !== null && (
        <ExitConfirmModal
          mode={pendingExit}
          onCancel={onExitCancel}
          onConfirm={onExitConfirm}
        />
      )}

      {lightboxIndex !== null && (
        <Lightbox
          index={lightboxIndex}
          slides={slides}
          onClose={() => onLightboxIndexChange(null)}
          onIndexChange={onLightboxIndexChange}
        />
      )}

    </>
  );
}

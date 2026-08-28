"use client";

import type { SlideData } from "@/types";
import Lightbox from "./Lightbox";
import RegenChatModal, { type RegenApplyMode } from "./RegenChatModal";
import ExitConfirmModal from "./ExitConfirmModal";

interface Props {
  slides: SlideData[];
  targetLang: string;
  pendingExit: "restart" | "cancel" | "render" | null;
  onExitCancel: () => void;
  onExitConfirm: () => void;
  lightboxIndex: number | null;
  onLightboxIndexChange: (index: number | null) => void;
  regeneratingSlide: number | null;
  regenAnchorText: string;
  onRegenApply: (index: number, mode: RegenApplyMode, content: string) => void;
  onRegenClose: () => void;
}

/** The three windows that lie over the steps: exit prompt, image view, rewrite chat. */
export default function ScreencastOverlays({
  slides, targetLang, pendingExit, onExitCancel, onExitConfirm,
  lightboxIndex, onLightboxIndexChange,
  regeneratingSlide, regenAnchorText, onRegenApply, onRegenClose,
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

      {regeneratingSlide !== null && slides[regeneratingSlide] && (
        <RegenChatModal
          slideIndex={regeneratingSlide}
          slideExtractedText={slides[regeneratingSlide].extractedText}
          currentScript={slides[regeneratingSlide].script || ""}
          anchorText={regenAnchorText}
          targetLang={targetLang}
          onApply={(mode, content) => onRegenApply(regeneratingSlide, mode, content)}
          onClose={onRegenClose}
        />
      )}
    </>
  );
}

"use client";

import type { SlideData } from "@/types";
import Lightbox from "./Lightbox";
import RegenChatModal, { type RegenTurn } from "@/components/regen/RegenChatModal";
import type { RegenApplyMode } from "@/components/regen/apply";
import { api } from "@/lib/api";
import ExitConfirmModal from "./ExitConfirmModal";

interface Props {
  slides: SlideData[];
  jobUuid: string;
  targetLang: string;
  glossaryJson: string;
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
  slides, jobUuid, targetLang, glossaryJson, pendingExit, onExitCancel, onExitConfirm,
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
          index={regeneratingSlide}
          anchorText={regenAnchorText}
          onSend={async (messages: RegenTurn[]) => {
            const result = await api.postJson<{ script: string }>("/api/screencast/regenerate-slide-script", {
              slide_text: slides[regeneratingSlide].extractedText,
              current_script: slides[regeneratingSlide].script || "",
              messages,
              selected_text: regenAnchorText || null,
              target_lang: targetLang,
              glossary_json: glossaryJson,
              slide_index: regeneratingSlide,
              slide_count: slides.length,
              // The slide may draw on the extra material assigned to it.
              translate_job_uuid: jobUuid || null,
              add_greeting: true,
              // Same policy as the generation: no closing platitude at the end.
              add_closing: false,
            });
            return result.script;
          }}
          onApply={(mode, content) => onRegenApply(regeneratingSlide, mode, content)}
          onClose={onRegenClose}
        />
      )}
    </>
  );
}

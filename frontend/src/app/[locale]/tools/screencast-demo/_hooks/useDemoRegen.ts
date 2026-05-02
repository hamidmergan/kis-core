"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import type { SlideData } from "@/types";


export function useDemoRegen(slides: SlideData[], setSlides: React.Dispatch<React.SetStateAction<SlideData[]>>) {
  const [regeneratingSlide, setRegeneratingSlide] = useState<number | null>(null);
  const [regenPrompt, setRegenPrompt] = useState("");
  const [regenProposal, setRegenProposal] = useState<string | null>(null);
  const [regenLoading, setRegenLoading] = useState(false);

  const openRegen = (index: number) => {
    setRegeneratingSlide(index);
    setRegenPrompt("");
    setRegenProposal(null);
  };

  const closeRegen = () => {
    setRegeneratingSlide(null);
    setRegenPrompt("");
    setRegenProposal(null);
  };

  const runRegen = async (index: number) => {
    setRegenLoading(true);
    setRegenProposal(null);
    try {
      const result = await api.postJson<{ script: string }>("/api/screencast/regenerate-slide-script", {
        slide_text: slides[index].extractedText,
        current_script: slides[index].script || "",
        user_prompt: regenPrompt || null,
        target_lang: "EN-US",
      });
      setRegenProposal(result.script);
    } catch {
      setRegenProposal("");
    } finally {
      setRegenLoading(false);
    }
  };

  const applyRegen = (index: number) => {
    if (regenProposal === null) return;
    setSlides((prev) => prev.map((s, i) => i === index ? { ...s, script: regenProposal } : s));
    closeRegen();
  };

  return {
    regeneratingSlide,
    regenPrompt,
    regenProposal,
    regenLoading,
    setRegenPrompt,
    setRegenProposal,
    openRegen,
    closeRegen,
    runRegen,
    applyRegen,
  };
}

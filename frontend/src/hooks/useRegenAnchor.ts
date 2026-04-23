"use client";

import { useCallback, useEffect, useState } from "react";

export function useRegenAnchor() {
  const [regeneratingSlide, setRegeneratingSlide] = useState<number | null>(null);
  const [anchorText, setAnchorText] = useState("");
  const [anchorSlide, setAnchorSlide] = useState<number | null>(null);

  useEffect(() => {
    const handler = () => {
      if (regeneratingSlide !== null) return;
      if (!window.getSelection()?.toString().trim()) {
        setAnchorText("");
        setAnchorSlide(null);
      }
    };
    document.addEventListener("selectionchange", handler);
    return () => document.removeEventListener("selectionchange", handler);
  }, [regeneratingSlide]);

  const open = useCallback((index: number) => setRegeneratingSlide(index), []);

  const close = useCallback(() => {
    setRegeneratingSlide(null);
    setAnchorText("");
    setAnchorSlide(null);
  }, []);

  const setAnchor = useCallback((slide: number | null, text: string) => {
    setAnchorSlide(slide);
    setAnchorText(text);
  }, []);

  return { regeneratingSlide, anchorText, anchorSlide, open, close, setAnchor };
}

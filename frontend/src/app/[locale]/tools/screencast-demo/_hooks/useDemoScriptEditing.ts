"use client";

import { useState } from "react";
import type { SlideData } from "@/types";


export function useDemoScriptEditing(slides: SlideData[], setSlides: React.Dispatch<React.SetStateAction<SlideData[]>>) {
  const [openAccordion, setOpenAccordion] = useState<number>(0);
  const [editingSlide, setEditingSlide] = useState<number | null>(null);
  const [editBuffer, setEditBuffer] = useState("");

  const startEdit = (index: number) => {
    setOpenAccordion(index);
    setEditingSlide(index);
    setEditBuffer(slides[index].script);
  };

  const saveEdit = (index: number) => {
    setSlides((prev) => prev.map((s, i) => i === index ? { ...s, script: editBuffer } : s));
    setEditingSlide(null);
    setEditBuffer("");
  };

  const cancelEdit = () => {
    setEditingSlide(null);
    setEditBuffer("");
  };

  const reset = () => {
    setOpenAccordion(0);
    setEditingSlide(null);
    setEditBuffer("");
  };

  return {
    openAccordion,
    editingSlide,
    editBuffer,
    setOpenAccordion,
    setEditBuffer,
    startEdit,
    saveEdit,
    cancelEdit,
    reset,
  };
}

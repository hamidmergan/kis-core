import { useCallback, useRef, useState } from "react";

interface UseScriptEditingOptions {
  onSave?: (index: number, newScript: string) => void;
}

export function useScriptEditing({ onSave }: UseScriptEditingOptions = {}) {
  const [openAccordion, setOpenAccordion] = useState<number>(0);
  const [editingSlide, setEditingSlide] = useState<number | null>(null);
  const [editBuffer, setEditBuffer] = useState("");

  const startEdit = useCallback((index: number, currentScript: string) => {
    setEditingSlide(index);
    setEditBuffer(currentScript);
  }, []);

  const cancelEdit = useCallback(() => {
    setEditingSlide(null);
    setEditBuffer("");
  }, []);

  const saveEdit = useCallback(
    (index: number) => {
      onSave?.(index, editBuffer);
      setEditingSlide(null);
      setEditBuffer("");
    },
    [editBuffer, onSave],
  );

  const toggleAccordion = useCallback(
    (index: number) => {
      if (editingSlide !== null) cancelEdit();
      setOpenAccordion((prev) => (prev === index ? -1 : index));
    },
    [editingSlide, cancelEdit],
  );

  const reset = useCallback(() => {
    setOpenAccordion(0);
    setEditingSlide(null);
    setEditBuffer("");
  }, []);

  return {
    openAccordion,
    editingSlide,
    editBuffer,
    setEditBuffer,
    startEdit,
    cancelEdit,
    saveEdit,
    toggleAccordion,
    reset,
  };
}

interface UseScriptAutosaveOptions {
  jobUuid: string;
  debounceMs?: number;
}

export function useScriptAutosave({ jobUuid, debounceMs = 1500 }: UseScriptAutosaveOptions) {
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  return useCallback(
    (updatedScripts: string[], accepted = false) => {
      if (!jobUuid) return;
      const send = (isAccepted: boolean) =>
        fetch(`/api/screencast/scripts/${jobUuid}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ scripts: updatedScripts, accepted: isAccepted }),
          credentials: "include",
        }).catch(() => {});

      if (accepted) {
        send(true);
        return;
      }
      if (timerRef.current) clearTimeout(timerRef.current);
      timerRef.current = setTimeout(() => send(false), debounceMs);
    },
    [jobUuid, debounceMs],
  );
}

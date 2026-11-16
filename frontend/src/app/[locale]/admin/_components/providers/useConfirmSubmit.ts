import { useEffect, useRef, useState } from "react";
import { backdropClose, newBackdropPress } from "@/components/ui/backdropClose";

/** Shared behaviour of the provider confirm dialogs: Escape, backdrop click and the pending confirm. */
export function useConfirmSubmit(onCancel: () => void, onConfirm: () => Promise<void> | void) {
  const [submitting, setSubmitting] = useState(false);
  const press = useRef(newBackdropPress()).current;

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !submitting) onCancel();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onCancel, submitting]);

  const handleBackdropClick = () => {
    if (!submitting) onCancel();
  };

  const handleConfirm = async () => {
    setSubmitting(true);
    try {
      await onConfirm();
    } finally {
      setSubmitting(false);
    }
  };

  return { submitting, handleConfirm, backdropProps: backdropClose(press, handleBackdropClick) };
}

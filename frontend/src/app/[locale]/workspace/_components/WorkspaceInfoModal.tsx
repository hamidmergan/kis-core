"use client";

import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import Modal from "@/components/ui/Modal";

/** Full description for a phone, where the row has no room to unfold it inline. */
export default function WorkspaceInfoModal({
  title,
  text,
  onClose,
}: {
  title: string;
  text: string;
  onClose: () => void;
}) {
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  if (!mounted) return null;

  return createPortal(
    <Modal open onClose={onClose} title={title} size="sm">
      <p className="text-sm whitespace-pre-wrap" style={{ color: "var(--foreground-soft)" }}>{text}</p>
    </Modal>,
    document.body,
  );
}

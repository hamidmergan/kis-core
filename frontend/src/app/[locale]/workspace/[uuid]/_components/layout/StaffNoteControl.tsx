"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { Info } from "@phosphor-icons/react";
import type { StaffNoteLink } from "../../_types";
import { StaffNoteViewModal } from "../sources/StaffNoteViewModal";
import { StaffNoteEditModal } from "../sources/StaffNoteEditModal";

interface StaffNoteControlProps {
  isOwner: boolean;
  text: string | null;
  links: StaffNoteLink[];
  onSave: (text: string | null, links: StaffNoteLink[]) => Promise<void>;
}

/** One button for everyone, owners edit the note behind it and everyone else reads it. */
export function StaffNoteControl({ isOwner, text, links, onSave }: StaffNoteControlProps) {
  const t = useTranslations("workspace.detail.sources");
  const [open, setOpen] = useState(false);
  const hasNote = Boolean(text?.trim()) || links.length > 0;
  // Without a note there is nothing to read, so readers get no button.
  if (!isOwner && !hasNote) return null;
  const label = !isOwner
    ? t("staffNote.expand")
    : hasNote
      ? t("staffNote.edit")
      : t("addStaffNote");
  return (
    <>
      <button
        type="button"
        data-tour="staff-note"
        onClick={() => setOpen(true)}
        className="w-7 h-7 flex items-center justify-center rounded-full btn-icon"
        style={{ backgroundColor: "var(--surface-dim)" }}
        title={label}
        aria-label={label}
      >
        <Info size={17} weight="regular" />
      </button>
      {isOwner ? (
        <StaffNoteEditModal
          open={open}
          initialText={text}
          initialLinks={links}
          onClose={() => setOpen(false)}
          onSave={onSave}
        />
      ) : (
        <StaffNoteViewModal
          open={open}
          text={text}
          links={links}
          onClose={() => setOpen(false)}
        />
      )}
    </>
  );
}

"use client";

import { useState } from "react";
import { PencilSimple } from "@phosphor-icons/react";
import IconButton from "@/components/ui/IconButton";
import { InlineRename } from "@/components/ui/InlineRename";

/** The name over a column, renamed in place. */
export default function SpeakerName({ name, onRename, renameLabel, errorText, readOnly = false }: {
  name: string;
  onRename: (next: string) => void;
  renameLabel: string;
  errorText: string;
  readOnly?: boolean;
}) {
  const [editing, setEditing] = useState(false);
  if (editing) {
    return (
      <span className="flex flex-1 min-w-0 max-w-[14rem]">
        <InlineRename
          value={name}
          onSave={async (next) => { onRename(next); }}
          onCancel={() => setEditing(false)}
          errorText={errorText}
        />
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1.5 min-w-0">
      <span className="text-sm font-semibold text-foreground truncate">{name}</span>
      {!readOnly && (
        <IconButton size="sm" onClick={() => setEditing(true)} aria-label={renameLabel} title={renameLabel}>
          <PencilSimple size={12} weight="bold" />
        </IconButton>
      )}
    </span>
  );
}

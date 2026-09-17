"use client";

import { FIELD } from "@/app/[locale]/tools/podcast/_steps/ContentStep";

/** Mirrors AIA_INSTRUCTION_MAX_CHARS in the backend, the schema cuts there too. */
export const INSTRUCTION_MAX_CHARS = 500;

/** The optional instruction to a tool, the same field the podcast has. */
export function InstructionField({ id, value, onChange, disabled, label, placeholder }: {
  id: string;
  value: string;
  onChange: (text: string) => void;
  disabled?: boolean;
  label: string;
  placeholder: string;
}) {
  return (
    <div className="w-full">
      <label htmlFor={id} className="block text-xs font-medium text-foreground-soft mb-1">
        {label}
      </label>
      <textarea
        id={id}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        rows={5}
        maxLength={INSTRUCTION_MAX_CHARS}
        placeholder={placeholder}
        disabled={disabled}
        className={`${FIELD} resize-y disabled:opacity-40`}
      />
    </div>
  );
}

/** What a finished result says about its instruction: the text, and whether it missed. */
export function InstructionNote({ instruction, unmatched, shownText, unmatchedText }: {
  instruction?: string | null;
  unmatched?: boolean;
  shownText: string;
  unmatchedText: string;
}) {
  if (!instruction && !unmatched) return null;
  return (
    <div className="flex flex-col gap-2">
      {unmatched && (
        <p className="rounded-md border border-warn-border bg-warn-bg px-3 py-2 text-sm text-warn-strong" role="status">
          {unmatchedText}
        </p>
      )}
      {instruction && (
        <p className="text-xs text-muted">{shownText}</p>
      )}
    </div>
  );
}

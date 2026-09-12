"use client";

import Select from "@/components/ui/Select";
import type { LangCode, LanguageOption } from "../_types";

/** The narrow language pill of a column. */
export default function LanguageSelect({ id, value, onChange, languages, label, disabled = false }: {
  id: string;
  value: LangCode;
  onChange: (code: LangCode) => void;
  languages: LanguageOption[];
  label: string;
  disabled?: boolean;
}) {
  return (
    <span className="inline-flex items-center shrink-0">
      <label htmlFor={id} className="sr-only">{label}</label>
      <Select<LangCode>
        id={id}
        size="sm"
        value={value}
        onChange={onChange}
        disabled={disabled}
        options={languages.map((l) => ({ value: l.id, label: l.label }))}
      />
    </span>
  );
}

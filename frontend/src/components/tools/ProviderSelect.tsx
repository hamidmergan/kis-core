"use client";

import Select from "@/components/ui/Select";
import type { FeatureProvider } from "@/hooks/useFeatureProviders";

type Props = {
  id: string;
  label: string;
  providers: FeatureProvider[];
  value: number | null;
  onChange: (id: number) => void;
  disabled?: boolean;
  className?: string;
  /** Shows the choice even with a single provider, so the person sees who writes. */
  showModel?: boolean;
};

/** Provider choice, with at most one provider it shows nothing unless showModel is set. */
export default function ProviderSelect({
  id,
  label,
  providers,
  value,
  onChange,
  disabled = false,
  className = "mb-4",
  showModel = false,
}: Props) {
  if (providers.length === 0 || (providers.length === 1 && !showModel)) return null;
  return (
    <div className={className}>
      <label htmlFor={id} className="block text-sm font-medium text-foreground-soft mb-2">
        {label}
      </label>
      <Select
        id={id}
        value={String(value ?? "")}
        onChange={(v) => onChange(Number(v))}
        disabled={disabled}
        options={providers.map((p) => ({
          value: String(p.id),
          label: p.name,
        }))}
      />
    </div>
  );
}

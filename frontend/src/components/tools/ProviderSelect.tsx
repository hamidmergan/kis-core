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
  /** Names the model behind each provider and shows even a single one, so the person sees which model writes. */
  showModel?: boolean;
};

/** Provider choice, with at most one provider it shows nothing unless the model is named. */
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
          label: showModel && p.model ? `${p.name} (${p.model})` : p.name,
        }))}
      />
    </div>
  );
}

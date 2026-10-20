"use client";

import { useTranslations } from "next-intl";
import Select from "@/components/ui/Select";
import ProviderAvailabilityHint from "@/components/tools/ProviderAvailabilityHint";
import type { FeatureProvider } from "@/hooks/useFeatureProviders";

/** Whether the provider field is shown: while loading, and afterwards only with a real choice. */
export function showProviderField(providers: FeatureProvider[], loading = false, showModel = false): boolean {
  return loading || providers.length > 1 || (providers.length === 1 && showModel);
}

type PickerProps = {
  id?: string;
  ariaLabel?: string;
  providers: FeatureProvider[];
  value: number | null;
  onChange: (id: number) => void;
  disabled?: boolean;
  loading?: boolean;
};

/** The provider dropdown with its availability hint, locked with a loading text until the list arrives. */
export function ProviderPicker({ id, ariaLabel, providers, value, onChange, disabled = false, loading = false }: PickerProps) {
  const t = useTranslations("common");
  return (
    <>
      <Select
        id={id}
        ariaLabel={ariaLabel}
        value={loading ? "" : String(value ?? "")}
        onChange={(v) => onChange(Number(v))}
        disabled={disabled || loading}
        placeholder={loading ? t("providersLoading") : undefined}
        options={loading ? [] : providers.map((p) => ({ value: String(p.id), label: p.name }))}
      />
      {!loading && <ProviderAvailabilityHint />}
    </>
  );
}

type Props = PickerProps & {
  id: string;
  label: string;
  className?: string;
  /** Shows the choice even with a single provider, so the person sees who writes. */
  showModel?: boolean;
};

/** Provider choice with its label, with at most one provider it shows nothing unless showModel is set. */
export default function ProviderSelect({ label, className = "mb-4", showModel = false, ...picker }: Props) {
  if (!showProviderField(picker.providers, picker.loading, showModel)) return null;
  return (
    <div className={className}>
      <label htmlFor={picker.id} className="block text-sm font-medium text-foreground-soft mb-2">
        {label}
      </label>
      <ProviderPicker {...picker} />
    </div>
  );
}

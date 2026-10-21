"use client";

import { useTranslations } from "next-intl";
import Select from "@/components/ui/Select";
import Spinner from "@/components/ui/Spinner";
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

/** A spinner in the shape of a dropdown, shown where a list is still loading. */
export function LoadingField() {
  const t = useTranslations("common");
  return (
    <div className="flex items-center rounded-md border border-border-soft px-3 py-2 text-sm">
      <Spinner size="sm" label={t("providersLoading")} />
    </div>
  );
}

/** The provider dropdown with its availability hint, replaced by a spinner until the list arrives. */
export function ProviderPicker({ id, ariaLabel, providers, value, onChange, disabled = false, loading = false }: PickerProps) {
  if (loading) return <LoadingField />;
  return (
    <>
      <Select
        id={id}
        ariaLabel={ariaLabel}
        value={String(value ?? "")}
        onChange={(v) => onChange(Number(v))}
        disabled={disabled}
        options={providers.map((p) => ({ value: String(p.id), label: p.name }))}
      />
      <ProviderAvailabilityHint />
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

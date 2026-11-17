"use client";

import { useEffect, useState } from "react";
import { api, backendApi } from "@/lib/api";
import type { ProviderOption } from "../_types";

const FALLBACK_PROVIDERS: ProviderOption[] = [{ id: -1, label: "THL myLab" }];

/** The providers from the platform, with a stand-in so the choice is always visible. */
export function useInterpreterConfig() {
  const [translationProviders, setTranslationProviders] = useState<ProviderOption[]>(FALLBACK_PROVIDERS);
  const [sttProviders, setSttProviders] = useState<ProviderOption[]>(FALLBACK_PROVIDERS);

  useEffect(() => {
    let active = true;
    api
      .fetch("/translate/config")
      .then((r) => (r.ok ? r.json() : null))
      .then((data: { providers?: ProviderOption[] } | null) => {
        if (active && data?.providers?.length) setTranslationProviders(data.providers);
      })
      .catch(() => {});
    backendApi
      .fetch("/transcription/providers")
      .then((r) => (r.ok ? r.json() : null))
      .then((data: { providers?: { id: number; name: string }[]; default_id?: number | null } | null) => {
        if (!active || !data?.providers?.length) return;
        // The admin default comes first, the page picks the first entry.
        const list = data.providers.map((p) => ({ id: p.id, label: p.name }));
        list.sort((a, b) => Number(b.id === data.default_id) - Number(a.id === data.default_id));
        setSttProviders(list);
      })
      .catch(() => {});
    return () => {
      active = false;
    };
  }, []);

  return { translationProviders, sttProviders };
}

"use client";

import { useEffect, useState } from "react";
import { backendApi } from "@/lib/api";

export type FeatureProvider = { id: number; name: string };

type ProvidersResponse = { providers: FeatureProvider[]; default_id: number | null };

/**
 * Load the reachable providers a tool may offer for a user-pickable feature.
 *
 * ``path`` is the backend listing endpoint (e.g. ``/transcription/providers``
 * or ``/image/providers/generate``). The dropdown should only be shown when
 * more than one provider comes back; an empty list means the tool falls back
 * to the admin default route. Mirrors the TTS picker.
 */
export function useFeatureProviders(path: string) {
  const [providers, setProviders] = useState<FeatureProvider[]>([]);
  const [providerId, setProviderId] = useState<number | null>(null);

  useEffect(() => {
    let active = true;
    backendApi
      .fetch(path)
      .then((r) => (r.ok ? r.json() : { providers: [], default_id: null }))
      .then((data: ProvidersResponse) => {
        if (!active) return;
        const list = data.providers ?? [];
        setProviders(list);
        if (list.length) setProviderId(data.default_id ?? list[0].id);
      })
      .catch(() => {
        // Leave the dropdown hidden — backend falls back to its default route.
      });
    return () => {
      active = false;
    };
  }, [path]);

  return { providers, providerId, setProviderId };
}

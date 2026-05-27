"use client";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useTranslations } from "next-intl";
import ProtectedRoute from "@/components/auth/ProtectedRoute";
import BackLink from "@/components/ui/BackLink";
import ProviderTab from "./_tabs/ProviderTab";
import type { ProviderWithVoices } from "./_utils";


function VoicesPageInner() {
  const t = useTranslations("tools.tts.voices");
  const searchParams = useSearchParams();
  const [providers, setProviders] = useState<ProviderWithVoices[]>([]);
  const [activeId, setActiveId] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("/api/tts/providers-with-voices", { credentials: "include" })
      .then((r) => r.json())
      .then((data) => {
        const list: ProviderWithVoices[] = data.providers ?? [];
        setProviders(list);
        const tabParam = searchParams.get("provider");
        const fromUrl = tabParam ? list.find((p) => p.id === Number(tabParam)) : null;
        setActiveId(fromUrl?.id ?? list[0]?.id ?? null);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const activeProvider = providers.find((p) => p.id === activeId);

  return (
    <ProtectedRoute>
      <div className="max-w-4xl mx-auto px-4 py-8">
        <BackLink />
        <h1 className="text-xl font-bold mb-1">{t("title")}</h1>

        {loading && <p className="text-sm text-muted mt-4">{t("loading")}</p>}

        {!loading && providers.length === 0 && (
          <p className="text-sm text-muted-soft mt-4">{t("noProviders")}</p>
        )}

        {providers.length > 0 && (
          <>
            <div className="flex gap-1 border-b border-border-soft mb-6">
              {providers.map((p) => (
                <button
                  key={p.id}
                  onClick={() => setActiveId(p.id)}
                  className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
                    activeId === p.id
                      ? "border-kb text-kb"
                      : "border-transparent text-muted hover:text-foreground-soft"
                  }`}
                >
                  {p.name}
                </button>
              ))}
            </div>

            {activeProvider && (
              <ProviderTab
                key={activeProvider.id}
                providerId={activeProvider.id}
                voices={activeProvider.voices}
              />
            )}
          </>
        )}
      </div>
    </ProtectedRoute>
  );
}


export default function VoicesPage() {
  return (
    <Suspense>
      <VoicesPageInner />
    </Suspense>
  );
}

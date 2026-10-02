"use client";

import { useCallback, useEffect, useState } from "react";
import { useFormatter, useTranslations } from "next-intl";
import ProtectedRoute from "@/components/auth/ProtectedRoute";
import { Link } from "@/i18n/navigation";
import CollapsibleCard from "@/components/ui/CollapsibleCard";
import Spinner from "@/components/ui/Spinner";
import { api, genericErrorMessage } from "@/lib/api";
import { ConsentNotice } from "./_components/ConsentNotice";
import { VendorCard } from "./_components/VendorCard";
import type { InterfacesOverview } from "./_types";

/** A person's own accounts at outside voice services, behind a notice accepted once. */
export default function InterfacesPage() {
  const t = useTranslations("interfaces");
  const format = useFormatter();
  // undefined while loading, null when the request failed or the permission is missing.
  const [data, setData] = useState<InterfacesOverview | null | undefined>(undefined);

  const load = useCallback(() => {
    api
      .fetch("/api/me/interfaces", { cache: "no-store" })
      .then((res) => (res.ok ? res.json() : null))
      .then((d) => setData(d ?? null))
      .catch(() => setData(null));
  }, []);
  useEffect(() => {
    load();
  }, [load]);

  const accept = async () => {
    const res = await api.fetch("/api/me/interfaces/consent", { method: "POST" });
    if (res.ok) load();
  };

  return (
    <ProtectedRoute>
      <main className="page-shell py-8">
        <h1 className="text-xl font-semibold mb-4">{t("title")}</h1>
        {data === undefined ? (
          <div className="flex justify-center py-16">
            <Spinner size="lg" />
          </div>
        ) : data === null ? (
          <p className="text-sm" style={{ color: "var(--muted)" }}>{genericErrorMessage()}</p>
        ) : (
          <div className="max-w-2xl mx-auto space-y-4">
            <div className="space-y-1">
              <p className="text-sm" style={{ color: "var(--foreground-soft)" }}>{t("intro")}</p>
              {/* The menu says interfaces, this line says which ones, so nobody looks for the LLM here. */}
              <p data-testid="interfaces-scope" className="text-sm font-semibold text-foreground">{t("scope")}</p>
              <p className="text-sm" style={{ color: "var(--foreground-soft)" }}>
                {t.rich("demo", {
                  link: (teil) => (
                    <Link href="/tools/podcast-demo" className="text-kb hover:underline">
                      {teil}
                    </Link>
                  ),
                })}
              </p>
            </div>
            {!data.consent.accepted ? (
              <div
                className="rounded-2xl p-5"
                style={{ border: "1px solid var(--border)", backgroundColor: "var(--surface)" }}
              >
                <ConsentNotice onAccept={accept} />
              </div>
            ) : (
              <>
                <CollapsibleCard
                  title={t("consent.acceptedOn", {
                    date: data.consent.accepted_at
                      ? format.dateTime(new Date(data.consent.accepted_at), { dateStyle: "medium" })
                      : "",
                  })}
                >
                  <ConsentNotice />
                </CollapsibleCard>
                <div className="pt-2">
                  <h3 className="text-base font-semibold">{t("voicesTitle")}</h3>
                  <p className="text-sm" style={{ color: "var(--foreground-soft)" }}>{t("voicesIntro")}</p>
                </div>
                {data.vendors.map((v) => (
                  <VendorCard
                    key={v.key}
                    vendor={v.key}
                    label={v.label}
                    connected={data.interfaces.find((i) => i.vendor === v.key)}
                    onChanged={load}
                  />
                ))}
              </>
            )}
          </div>
        )}
      </main>
    </ProtectedRoute>
  );
}

"use client";

import { useEffect, useState } from "react";
import { useFormatter, useTranslations } from "next-intl";
import { ArrowClockwise, Trash } from "@phosphor-icons/react";
import { api, genericErrorMessage, parseDetail } from "@/lib/api";
import type { Credit, OwnInterface } from "../_types";

async function detailOf(res: Response): Promise<string> {
  try {
    return parseDetail((await res.json())?.detail, genericErrorMessage());
  } catch {
    return genericErrorMessage();
  }
}

/** One outside voice service: connect it with a key, or see and manage the connection. */
export function VendorCard({
  vendor,
  label,
  connected,
  onChanged,
}: {
  vendor: string;
  label: string;
  connected: OwnInterface | undefined;
  onChanged: () => void;
}) {
  const t = useTranslations("interfaces.vendor");
  const format = useFormatter();
  const [key, setKey] = useState("");
  const [replacing, setReplacing] = useState(false);
  const [removing, setRemoving] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  // undefined while asking, null when the service does not tell.
  const [credit, setCredit] = useState<Credit | null | undefined>(undefined);

  useEffect(() => {
    if (!connected) return;
    let cancelled = false;
    setCredit(undefined);
    api
      .fetch(`/api/me/interfaces/${connected.id}/credit`, { cache: "no-store" })
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (!cancelled) setCredit(data?.credit ?? null);
      })
      .catch(() => {
        if (!cancelled) setCredit(null);
      });
    return () => {
      cancelled = true;
    };
  }, [connected]);

  const run = async (request: () => Promise<Response>) => {
    if (busy) return;
    setBusy(true);
    setError("");
    try {
      const res = await request();
      if (!res.ok) {
        setError(await detailOf(res));
        return;
      }
      setKey("");
      setReplacing(false);
      setRemoving(false);
      onChanged();
    } catch {
      setError(genericErrorMessage());
    } finally {
      setBusy(false);
    }
  };

  const connect = () =>
    run(() =>
      api.fetch("/api/me/interfaces", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ vendor, api_key: key.trim() }),
      }),
    );
  const refresh = () => run(() => api.fetch(`/api/me/interfaces/${connected!.id}/refresh`, { method: "POST" }));
  const remove = () => run(() => api.fetch(`/api/me/interfaces/${connected!.id}`, { method: "DELETE" }));

  const showForm = !connected || replacing;

  return (
    <section
      data-testid={`interface-${vendor}`}
      className="rounded-2xl p-5 space-y-3"
      style={{ border: "1px solid var(--border)", backgroundColor: "var(--surface)" }}
    >
      <div className="flex items-center justify-between gap-3">
        <h3 className="text-base font-semibold">{label}</h3>
        <span className="text-xs font-medium" style={{ color: connected ? "var(--kb-dark)" : "var(--muted)" }}>
          {connected ? t("connected") : t("notConnected")}
        </span>
      </div>

      {connected && (
        <div className="text-sm space-y-1" style={{ color: "var(--foreground-soft)" }}>
          <p>{t("keyEnding", { chars: connected.key_last_chars })}</p>
          <p>{t("voices", { count: connected.voices.length })}</p>
          {credit === undefined ? null : credit ? (
            <p data-testid={`interface-${vendor}-credit`}>
              {t("credit", {
                left: format.number(Math.max(0, credit.limit - credit.used)),
                limit: format.number(credit.limit),
                unit: t(`units.${credit.unit}`),
              })}
            </p>
          ) : (
            <p>{t("creditUnknown")}</p>
          )}
        </div>
      )}

      {showForm && (
        <div className="space-y-2">
          <label htmlFor={`key-${vendor}`} className="block text-sm font-medium text-foreground-soft">
            {t("keyLabel")}
          </label>
          <div className="flex flex-col sm:flex-row gap-2">
            <input
              id={`key-${vendor}`}
              type="password"
              autoComplete="off"
              value={key}
              onChange={(e) => setKey(e.target.value)}
              disabled={busy}
              className="flex-1 min-w-0 px-3 py-2 border border-border rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-kb focus:border-transparent disabled:opacity-50"
            />
            <button
              type="button"
              onClick={() => void connect()}
              disabled={busy || key.trim().length < 8}
              className="px-4 py-2 text-sm font-medium rounded-md btn-primary disabled:opacity-50"
            >
              {busy ? t("checking") : t("connect")}
            </button>
            {replacing && (
              <button
                type="button"
                onClick={() => setReplacing(false)}
                disabled={busy}
                className="px-4 py-2 text-sm font-medium rounded-md btn-cancel"
              >
                {t("cancel")}
              </button>
            )}
          </div>
          <p className="text-xs text-muted-soft">{t(`keyHint.${vendor}`)}</p>
        </div>
      )}

      {connected && removing && (
        <div className="flex flex-wrap items-center gap-2 pt-1">
          <span className="text-sm text-error">{t("removeConfirm", { vendor: label })}</span>
          <button
            type="button"
            onClick={() => void remove()}
            disabled={busy}
            className="px-3 py-1.5 text-sm font-medium rounded-md btn-danger"
          >
            {t("removeYes")}
          </button>
          <button
            type="button"
            onClick={() => setRemoving(false)}
            disabled={busy}
            className="px-3 py-1.5 text-sm font-medium rounded-md btn-cancel"
          >
            {t("cancel")}
          </button>
        </div>
      )}

      {connected && !replacing && !removing && (
        <div className="flex flex-wrap gap-2 pt-1">
          <button
            type="button"
            onClick={() => void refresh()}
            disabled={busy}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium rounded-md btn-cancel"
          >
            <ArrowClockwise size={14} weight="bold" aria-hidden="true" />
            {t("refresh")}
          </button>
          <button
            type="button"
            onClick={() => setReplacing(true)}
            disabled={busy}
            className="px-3 py-1.5 text-sm font-medium rounded-md btn-cancel"
          >
            {t("replaceKey")}
          </button>
          <button
            type="button"
            onClick={() => setRemoving(true)}
            disabled={busy}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium rounded-md btn-danger"
          >
            <Trash size={14} weight="bold" aria-hidden="true" />
            {t("remove")}
          </button>
        </div>
      )}

      {error && (
        <p className="text-sm text-error" role="alert">
          {error}
        </p>
      )}
    </section>
  );
}

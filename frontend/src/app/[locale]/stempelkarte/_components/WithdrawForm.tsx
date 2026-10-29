"use client";

import { useState, type FormEvent } from "react";
import { useTranslations } from "next-intl";
import { eventApi } from "@/lib/event/api";

/** Takes an address out of the raffle, the page answers the same whether the address was in or not. */
export default function WithdrawForm() {
  const t = useTranslations("eventStamp.withdraw");
  const [value, setValue] = useState("");
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (busy || !value.trim()) return;
    setBusy(true);
    try {
      await eventApi.raffleWithdraw(value);
      setDone(true);
      setValue("");
    } catch (err) {
      setError((err instanceof Error && err.message) || t("failed"));
    } finally {
      setBusy(false);
    }
  };

  return (
    <main className="max-w-3xl mx-auto px-4 py-6 sm:py-8 flex flex-col gap-6" data-testid="raffle-withdraw">
      <div>
        <h1 className="text-2xl font-semibold tracking-[-0.01em] text-foreground">{t("title")}</h1>
        <p className="text-base text-foreground-soft mt-1">{t("intro")}</p>
      </div>
      {done ? (
        <p className="text-base text-foreground" role="status" data-testid="withdraw-done">
          {t("done")}
        </p>
      ) : (
        <form onSubmit={submit} className="flex flex-col gap-2">
          <label htmlFor="withdraw-email" className="text-sm font-medium text-foreground">
            {t("email")}
          </label>
          <div className="flex gap-2">
            <input
              id="withdraw-email"
              type="email"
              required
              autoComplete="email"
              value={value}
              onChange={(e) => setValue(e.target.value)}
              disabled={busy}
              className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground focus:outline-none focus:border-kb disabled:opacity-50"
              data-testid="withdraw-email"
            />
            <button
              type="submit"
              disabled={busy || !value.trim()}
              className="px-3 py-2 text-sm btn-primary rounded-md transition-colors whitespace-nowrap disabled:opacity-60"
              data-testid="withdraw-submit"
            >
              {t("submit")}
            </button>
          </div>
          {error && (
            <p className="text-sm text-error" role="alert">
              {error}
            </p>
          )}
        </form>
      )}
    </main>
  );
}

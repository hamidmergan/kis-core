"use client";

import { useState, type FormEvent } from "react";
import { useTranslations } from "next-intl";
import Checkbox from "@/components/ui/Checkbox";
import { Link } from "@/i18n/navigation";
import { ROUTES } from "@/lib/event/routes";
import type { PublicRaffle } from "@/lib/event/types";
import { useText2 } from "@/lib/event/useText2";

/** Under a full card: the raffle with address field and consent box, the confirmation once the visitor is in. */
export default function RaffleEntry({
  raffle,
  email,
  enter,
}: {
  raffle: PublicRaffle;
  email: string | null;
  enter: (email: string) => Promise<string | null>;
}) {
  const t = useTranslations("eventStamp.raffle");
  const text = useText2();
  const [value, setValue] = useState("");
  const [agreed, setAgreed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (busy || !agreed || !value.trim()) return;
    setBusy(true);
    const fehler = await enter(value);
    setBusy(false);
    setError(fehler === null ? null : fehler || t("failed"));
  };

  return (
    <section className="flex flex-col gap-3 rounded-2xl border border-border p-5" data-testid="raffle">
      <h2 className="text-lg font-semibold text-foreground">{text(raffle.title)}</h2>
      <p className="text-sm text-foreground-soft">{text(raffle.text)}</p>
      {email ? (
        <>
          <p className="text-base font-medium text-foreground" data-testid="raffle-done">
            {text(raffle.done)}
          </p>
          <p className="text-xs text-muted">{t("entered", { email })}</p>
          <p className="text-xs text-muted">
            {t("withdrawHint")}{" "}
            <Link href={ROUTES.withdraw} className="underline text-foreground">
              {t("withdrawLink")}
            </Link>
          </p>
        </>
      ) : (
        <form onSubmit={submit} className="flex flex-col gap-3">
          <label htmlFor="raffle-email" className="text-sm font-medium text-foreground">
            {t("email")}
          </label>
          <input
            id="raffle-email"
            type="email"
            required
            autoComplete="email"
            value={value}
            onChange={(e) => setValue(e.target.value)}
            disabled={busy}
            className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground focus:outline-none focus:border-kb disabled:opacity-50"
            data-testid="raffle-email"
          />
          <Checkbox
            checked={agreed}
            onChange={setAgreed}
            label={text(raffle.consent)}
            className="items-start text-left"
            labelClassName="whitespace-normal! text-sm text-foreground text-left"
          />
          <button
            type="submit"
            disabled={busy || !agreed || !value.trim()}
            className="self-start px-4 py-2 text-sm btn-primary rounded-md transition-colors disabled:opacity-60"
            data-testid="raffle-submit"
          >
            {t("submit")}
          </button>
          {error && (
            <p className="text-sm text-error" role="alert" data-testid="raffle-error">
              {error}
            </p>
          )}
        </form>
      )}
    </section>
  );
}

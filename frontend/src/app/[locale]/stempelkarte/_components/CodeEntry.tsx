"use client";

import { useEffect, useState, type FormEvent } from "react";
import { useTranslations } from "next-intl";
import { CODE_LENGTH } from "@/lib/event/codes";
import type { Card } from "@/lib/event/types";
import type { CodeOutcome } from "@/lib/event/useStampCard";

/** A stand code stamps that stand, the server counts the misses and locks the field for a while. */
export default function CodeEntry({
  card,
  submitCode,
  onStamped,
  onWrong,
}: {
  card: Card;
  submitCode: (code: string) => Promise<CodeOutcome | null>;
  onStamped: (id: string) => void;
  onWrong: () => void;
}) {
  const t = useTranslations("eventStamp.code");
  const [value, setValue] = useState("");
  const [wrong, setWrong] = useState(false);
  const [busy, setBusy] = useState(false);
  const [remainingMs, setRemainingMs] = useState(0);

  useEffect(() => {
    const tick = () => setRemainingMs(card.lockedUntil ? Math.max(0, card.lockedUntil - Date.now()) : 0);
    tick();
    if (!card.lockedUntil) return;
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [card.lockedUntil]);

  const locked = remainingMs > 0;
  const seconds = Math.ceil(remainingMs / 1000);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (locked || busy || value.length < CODE_LENGTH) return;
    setBusy(true);
    const outcome = await submitCode(value);
    setBusy(false);
    setValue("");
    if (outcome?.result === "stamped") {
      setWrong(false);
      onStamped(outcome.stationId);
      return;
    }
    setWrong(true);
    onWrong();
  };

  return (
    <section className="flex flex-col gap-2" data-testid="code-entry">
      <form onSubmit={submit} className="flex flex-col gap-2">
        <label htmlFor="event-code" className="text-sm font-medium text-foreground">
          {t("label")}
        </label>
        <div className="flex gap-2">
          <input
            id="event-code"
            value={value}
            onChange={(e) => setValue(e.target.value.toUpperCase())}
            maxLength={CODE_LENGTH}
            autoCapitalize="characters"
            autoCorrect="off"
            autoComplete="off"
            spellCheck={false}
            disabled={locked || busy}
            className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground focus:outline-none focus:border-kb disabled:opacity-50 uppercase tracking-[0.2em]"
            data-testid="code-input"
          />
          <button
            type="submit"
            disabled={locked || busy || value.length < CODE_LENGTH}
            className="px-3 py-2 text-sm btn-primary rounded-md transition-colors whitespace-nowrap disabled:opacity-60"
            data-testid="code-submit"
          >
            {t("submit")}
          </button>
        </div>
      </form>
      {locked ? (
        <p className="text-sm text-error tabular-nums" data-testid="code-locked">
          {t("locked", { seconds })}
        </p>
      ) : wrong ? (
        <p className="text-sm text-error" data-testid="code-wrong">
          {t("wrong")} {card.attemptsLeft > 0 && t("attemptsLeft", { n: card.attemptsLeft })}
        </p>
      ) : (
        <p className="text-xs text-muted">{t("hint")}</p>
      )}
    </section>
  );
}

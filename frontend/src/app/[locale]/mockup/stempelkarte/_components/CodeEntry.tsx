"use client";

import { useEffect, useState, type FormEvent } from "react";
import { useTranslations } from "next-intl";
import Modal from "@/components/ui/Modal";
import { MOCKUP_ICONS } from "../../_lib/icons";
import { CODE_LENGTH, MAX_ATTEMPTS, afterWrongCode, codeMatches, lockRemainingMs } from "../../_lib/masterCode";
import { useMockup } from "../../_lib/store";
import { useText2 } from "../../_lib/useText2";

/** Master code from the poster, a hit opens the stand picker, five misses lock the field for a while. */
export default function CodeEntry({ onStamp, onWrong }: { onStamp: (id: string) => void; onWrong: () => void }) {
  const t = useTranslations("mockup.stamp.code");
  const text = useText2();
  const [config] = useMockup("config");
  const [card, updateCard] = useMockup("card");
  const [value, setValue] = useState("");
  const [wrong, setWrong] = useState(false);
  const [pickOpen, setPickOpen] = useState(false);
  const [remainingMs, setRemainingMs] = useState(0);

  useEffect(() => {
    const tick = () => setRemainingMs(lockRemainingMs(card, Date.now()));
    tick();
    if (!card.lockUntil) return;
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [card]);

  const locked = remainingMs > 0;
  const seconds = Math.ceil(remainingMs / 1000);

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (locked || value.length < CODE_LENGTH) return;
    if (codeMatches(value, config.masterCode)) {
      setWrong(false);
      setValue("");
      setPickOpen(true);
      return;
    }
    updateCard((c) => afterWrongCode(c, Date.now()));
    setWrong(true);
    setValue("");
    onWrong();
  };

  const pick = (id: string) => {
    setPickOpen(false);
    onStamp(id);
  };

  return (
    <section className="flex flex-col gap-2" data-testid="code-entry">
      <form onSubmit={submit} className="flex flex-col gap-2">
        <label htmlFor="mockup-code" className="text-sm font-medium text-foreground">
          {t("label")}
        </label>
        <div className="flex gap-2">
          <input
            id="mockup-code"
            value={value}
            onChange={(e) => setValue(e.target.value.toUpperCase())}
            maxLength={CODE_LENGTH}
            autoCapitalize="characters"
            autoCorrect="off"
            autoComplete="off"
            spellCheck={false}
            disabled={locked}
            placeholder={t("placeholder")}
            className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground focus:outline-none focus:border-kb disabled:opacity-50 uppercase tracking-[0.2em]"
            data-testid="code-input"
          />
          <button
            type="submit"
            disabled={locked || value.length < CODE_LENGTH}
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
          {t("wrong")} {card.failedAttempts > 0 && t("attemptsLeft", { n: MAX_ATTEMPTS - card.failedAttempts })}
        </p>
      ) : (
        <p className="text-xs text-muted">{t("hint")}</p>
      )}
      <Modal open={pickOpen} onClose={() => setPickOpen(false)} title={t("pickTitle")} size="sm">
        <p className="text-sm text-foreground-soft mb-3">{t("pickHint")}</p>
        <ul className="flex flex-col gap-2" data-testid="station-picker">
          {config.stations.map((station) => {
            const Icon = MOCKUP_ICONS[station.icon];
            const done = station.id in card.stamped;
            return (
              <li key={station.id}>
                <button
                  type="button"
                  onClick={() => pick(station.id)}
                  className="w-full flex items-center gap-3 rounded-xl border-2 border-border bg-background p-3 text-left text-foreground hover:border-kb transition-colors"
                  data-testid={`pick-${station.id}`}
                >
                  <span className="flex items-center justify-center w-10 h-10 shrink-0 rounded-full bg-kb text-on-accent">
                    <Icon size={20} weight="bold" aria-hidden="true" />
                  </span>
                  <span className="flex-1 min-w-0">
                    <span className="block text-sm font-semibold">{text(station.name)}</span>
                    {done && <span className="block text-xs text-muted">{t("alreadyStamped")}</span>}
                  </span>
                </button>
              </li>
            );
          })}
        </ul>
      </Modal>
    </section>
  );
}

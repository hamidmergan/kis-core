"use client";

import { useCallback, useEffect, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { useAdminPerms } from "@/app/[locale]/admin/_nav/AdminAuth";
import { SettingCard } from "@/app/[locale]/admin/_settings/fields";
import ConfirmDialog from "@/components/event/ConfirmDialog";
import { eventApi } from "@/lib/event/api";
import { ROUTES } from "@/lib/event/routes";
import type { RaffleEntry } from "@/lib/event/types";
import { isFullAdmin } from "@/lib/permissions";
import { BTN_SECONDARY, INPUT } from "./fields";

const ZONE = "Europe/Berlin";

/** The addresses in the raffle with the withdraw link to send along, the list as CSV, and the way back to zero. */
export default function RaffleEntriesCard() {
  const t = useTranslations("eventAdmin.raffle");
  const locale = useLocale();
  const fullAdmin = isFullAdmin(useAdminPerms());
  const [entries, setEntries] = useState<RaffleEntry[] | null>(null);
  const [failed, setFailed] = useState(false);
  const [confirmAll, setConfirmAll] = useState(false);
  const [copied, setCopied] = useState<"link" | "text" | null>(null);
  const [origin, setOrigin] = useState("");

  // The origin exists only in the browser, the first render on the server has none.
  useEffect(() => setOrigin(window.location.origin), []);
  const url = `${origin}${ROUTES.withdraw}`;
  const snippet = t("snippet", { url });

  const load = useCallback(() => {
    eventApi
      .adminRaffleEntries()
      .then((r) => setEntries(r.entries))
      .catch(() => setFailed(true));
  }, []);
  useEffect(() => load(), [load]);

  const copy = async (what: "link" | "text", value: string) => {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(what);
      setTimeout(() => setCopied(null), 1500);
    } catch {
      // Clipboard blocked, the text stays on screen to select by hand.
    }
  };

  const run = async (call: () => Promise<unknown>) => {
    try {
      await call();
      load();
    } catch {
      setFailed(true);
    }
  };

  const download = () => {
    if (!entries) return;
    // A leading formula character would run in a spreadsheet, the apostrophe keeps it as text.
    const cell = (s: string) => `"${(/^[=+\-@]/.test(s) ? `'${s}` : s).replace(/"/g, '""')}"`;
    const lines = ["email,entered_at", ...entries.map((e) => `${cell(e.email)},${new Date(e.enteredAt).toISOString()}`)];
    const blob = new Blob([lines.join("\n")], { type: "text/csv;charset=utf-8" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "verlosung.csv";
    a.click();
    URL.revokeObjectURL(a.href);
  };

  const when = new Intl.DateTimeFormat(locale, { timeZone: ZONE, dateStyle: "short", timeStyle: "short" });

  return (
    <SettingCard title={t("entriesTitle")} description={entries ? t("count", { n: entries.length }) : ""}>
      <div className="mt-4 flex flex-col gap-5" data-testid="raffle-entries">
        <div className="flex flex-col gap-2">
          <p className="text-sm text-foreground">{t("linkTitle")}</p>
          <p className="text-xs text-muted">{t("linkHint")}</p>
          <div className="flex items-center gap-2">
            <input type="text" readOnly value={url} className={`${INPUT} font-mono`} data-testid="raffle-link" />
            <button type="button" onClick={() => void copy("link", url)} className={BTN_SECONDARY}>
              {copied === "link" ? t("copied") : t("copyLink")}
            </button>
          </div>
          <p className="text-sm text-foreground mt-2">{t("snippetTitle")}</p>
          <textarea readOnly value={snippet} rows={3} className={`${INPUT} resize-y`} data-testid="raffle-snippet" />
          <button type="button" onClick={() => void copy("text", snippet)} className={`${BTN_SECONDARY} self-start`}>
            {copied === "text" ? t("copied") : t("copyText")}
          </button>
        </div>

        {failed ? (
          <p className="text-sm text-error">{t("loadFailed")}</p>
        ) : !entries ? (
          <p className="text-sm text-muted">{t("loading")}</p>
        ) : (
          <ul className="flex flex-col divide-y divide-border" data-testid="raffle-list">
            {entries.map((e) => (
              <li key={e.id} className="flex flex-wrap items-center justify-between gap-2 py-2">
                <div className="min-w-0 flex-1 basis-64">
                  <p className="text-sm text-foreground truncate">{e.email}</p>
                  <p className="text-xs text-muted tabular-nums">{when.format(new Date(e.enteredAt))}</p>
                </div>
                <button
                  type="button"
                  onClick={() => void run(() => eventApi.adminDeleteRaffleEntry(e.id))}
                  className={BTN_SECONDARY}
                  aria-label={t("deleteAria", { email: e.email })}
                >
                  {t("delete")}
                </button>
              </li>
            ))}
          </ul>
        )}

        <div className="flex flex-wrap items-center justify-between gap-3">
          <button type="button" disabled={!entries?.length} onClick={download} className={BTN_SECONDARY} data-testid="raffle-csv">
            {t("csv")}
          </button>
          {fullAdmin && (
            <button
              type="button"
              disabled={!entries?.length}
              onClick={() => setConfirmAll(true)}
              className="px-4 py-2 text-sm btn-danger rounded-lg disabled:opacity-50"
              data-testid="raffle-delete-all"
            >
              {t("all")}
            </button>
          )}
        </div>
      </div>
      {confirmAll && (
        <ConfirmDialog
          title={t("allConfirmTitle")}
          text={t("allConfirmText")}
          confirmLabel={t("all")}
          onConfirm={() => {
            setConfirmAll(false);
            void run(eventApi.adminDeleteAllRaffleEntries);
          }}
          onCancel={() => setConfirmAll(false)}
          testId="raffle-delete-all-confirm"
        />
      )}
    </SettingCard>
  );
}

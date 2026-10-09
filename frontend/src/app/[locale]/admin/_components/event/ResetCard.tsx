"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { useAdminPerms } from "@/app/[locale]/admin/_nav/AdminAuth";
import { SettingCard } from "@/app/[locale]/admin/_settings/fields";
import ConfirmDialog from "@/components/event/ConfirmDialog";
import { eventApi } from "@/lib/event/api";
import { isFullAdmin } from "@/lib/permissions";
import { BTN_SECONDARY, INPUT } from "./fields";

type Status = "idle" | "mine" | "one" | "oneNotFound" | "all" | "failed";

/** Three ways back to zero: the card of this browser for another test run, one visitor's card by their own code, and for full admins every card at once. */
export default function ResetCard({ onDone }: { onDone: () => void }) {
  const t = useTranslations("eventAdmin.reset");
  const fullAdmin = isFullAdmin(useAdminPerms());
  const [confirmAll, setConfirmAll] = useState(false);
  const [status, setStatus] = useState<Status>("idle");
  const [busy, setBusy] = useState(false);
  const [oneCode, setOneCode] = useState("");

  const run = async (call: () => Promise<unknown>, done: Status, onSuccess?: () => void) => {
    setBusy(true);
    try {
      await call();
      setStatus(done);
      onDone();
      onSuccess?.();
    } catch (err) {
      setStatus((err as { status?: number }).status === 404 ? "oneNotFound" : "failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <SettingCard title={t("title")} description={t("description")}>
      <div className="mt-4 flex flex-col gap-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="min-w-0 flex-1 basis-64">
            <p className="text-sm text-foreground">{t("mineTitle")}</p>
            <p className="text-xs text-muted">{t("mineText")}</p>
          </div>
          <button
            type="button"
            disabled={busy}
            onClick={() => void run(eventApi.adminResetMyCard, "mine")}
            className={BTN_SECONDARY}
            data-testid="reset-mine"
          >
            {t("mine")}
          </button>
        </div>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="min-w-0 flex-1 basis-64">
            <p className="text-sm text-foreground">{t("oneTitle")}</p>
            <p className="text-xs text-muted">{t("oneText")}</p>
          </div>
          <div className="flex items-center gap-2">
            <input
              type="text"
              value={oneCode}
              onChange={(e) => setOneCode(e.target.value)}
              placeholder={t("onePlaceholder")}
              className={`${INPUT} w-32`}
              data-testid="reset-one-input"
            />
            <button
              type="button"
              disabled={busy || !oneCode.trim()}
              onClick={() => void run(() => eventApi.adminResetOneCard(oneCode.trim()), "one", () => setOneCode(""))}
              className={BTN_SECONDARY}
              data-testid="reset-one"
            >
              {t("one")}
            </button>
          </div>
        </div>
        {fullAdmin && (
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="min-w-0 flex-1 basis-64">
              <p className="text-sm text-foreground">{t("allTitle")}</p>
              <p className="text-xs text-muted">{t("allText")}</p>
            </div>
            <button
              type="button"
              disabled={busy}
              onClick={() => setConfirmAll(true)}
              className="px-4 py-2 text-sm btn-danger rounded-lg disabled:opacity-50"
              data-testid="reset-all"
            >
              {t("all")}
            </button>
          </div>
        )}
        <p
          className={`text-xs h-4 ${status === "failed" || status === "oneNotFound" ? "text-error" : "text-muted"}`}
          role="status"
          data-testid="reset-status"
        >
          {status === "mine" && t("mineDone")}
          {status === "one" && t("oneDone")}
          {status === "oneNotFound" && t("oneNotFound")}
          {status === "all" && t("allDone")}
          {status === "failed" && t("failed")}
        </p>
      </div>
      {confirmAll && (
        <ConfirmDialog
          title={t("allConfirmTitle")}
          text={t("allConfirmText")}
          confirmLabel={t("all")}
          onConfirm={() => {
            setConfirmAll(false);
            void run(eventApi.adminResetAllStamps, "all");
          }}
          onCancel={() => setConfirmAll(false)}
          testId="reset-all-confirm"
        />
      )}
    </SettingCard>
  );
}

"use client";

/** The access codes for the test rounds. */

import { useCallback, useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { Check, Copy } from "@phosphor-icons/react";
import Spinner from "@/components/ui/Spinner";
import StatusMark from "@/components/ui/StatusMark";
import Modal from "@/components/ui/Modal";
import type { StatusTone } from "@/lib/jobStatusDisplay";
import { copyTextFromPromise } from "@/lib/clipboard";
import CreateAccessCodeDialog from "./CreateAccessCodeDialog";

type Zustand = "active" | "disabled" | "expired" | "full";

type Code = {
  id: number;
  code: string;
  label: string;
  role: string;
  custom_role_id: number | null;
  max_uses: number;
  used_count: number;
  valid_until: string;
  access_days: number;
  active: boolean;
  created_at: string;
  status: Zustand;
};

const TON: Record<Zustand, StatusTone> = {
  active: "brand",
  disabled: "muted",
  expired: "muted",
  full: "success",
};

function datum(wert: string): string {
  return new Date(wert).toLocaleDateString("de-DE");
}

export default function AccessCodesTab() {
  const t = useTranslations("admin.accessCodes");
  const [codes, setCodes] = useState<Code[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [dialogOffen, setDialogOffen] = useState(false);
  const [kopiert, setKopiert] = useState<number | null>(null);
  const [loeschen, setLoeschen] = useState<Code | null>(null);

  const laden = useCallback(() => {
    fetch("/api/admin/access-codes", { credentials: "include" })
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error("load"))))
      .then((d) => setCodes(d.codes ?? []))
      .catch(() => setError(t("loadError")))
      .finally(() => setLoading(false));
  }, [t]);

  useEffect(laden, [laden]);

  function kopieren(code: Code) {
    copyTextFromPromise(Promise.resolve(code.code));
    setKopiert(code.id);
    setTimeout(() => setKopiert(null), 1500);
  }

  async function umschalten(code: Code) {
    const r = await fetch(`/api/admin/access-codes/${code.id}`, {
      method: "PATCH",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ active: !code.active }),
    });
    if (!r.ok) {
      setError(t("saveError"));
      return;
    }
    laden();
  }

  async function wirklichLoeschen(code: Code) {
    setLoeschen(null);
    const r = await fetch(`/api/admin/access-codes/${code.id}`, {
      method: "DELETE",
      credentials: "include",
    });
    if (!r.ok) {
      setError(t("saveError"));
      return;
    }
    setCodes((prev) => prev.filter((e) => e.id !== code.id));
  }

  const aktiv = codes.filter((e) => e.status === "active").length;

  return (
    <div className="space-y-3" data-testid="access-codes-tab">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="text-xs text-muted-soft">{t("summary", { n: codes.length, aktiv })}</span>
        <button
          type="button"
          onClick={() => setDialogOffen(true)}
          data-testid="access-code-create"
          className="px-3 py-2 text-sm bg-kb text-white rounded-md whitespace-nowrap"
        >
          {t("createButton")}
        </button>
      </div>

      {error && <p className="text-xs text-error">{error}</p>}

      {loading ? (
        <Spinner className="flex justify-center py-12" />
      ) : codes.length === 0 ? (
        <p className="text-sm text-muted-soft text-center py-8">{t("empty")}</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm border border-border-soft rounded-xl overflow-hidden">
            <thead className="bg-surface text-xs text-muted uppercase">
              <tr>
                <th className="px-4 py-3 text-left">{t("colLabel")}</th>
                <th className="px-4 py-3 text-left">{t("colCode")}</th>
                <th className="px-4 py-3 text-left">{t("colUsed")}</th>
                <th className="px-4 py-3 text-left">{t("colValid")}</th>
                <th className="px-4 py-3 text-left">{t("colAccess")}</th>
                <th className="px-4 py-3 text-left">{t("colStatus")}</th>
                <th className="px-4 py-3 text-left">{t("colActions")}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border-soft bg-background">
              {codes.map((e) => (
                <tr key={e.id}>
                  <td className="px-4 py-3 font-medium text-foreground">{e.label}</td>
                  <td className="px-4 py-3 font-mono text-foreground-soft">{e.code}</td>
                  <td className="px-4 py-3 text-foreground-soft">{e.used_count} / {e.max_uses}</td>
                  <td className="px-4 py-3 text-foreground-soft">{datum(e.valid_until)}</td>
                  <td className="px-4 py-3 text-foreground-soft">{t("accessDays", { n: e.access_days })}</td>
                  <td className="px-4 py-3">
                    <StatusMark tone={TON[e.status]} className="text-xs">
                      {t(`status${e.status[0].toUpperCase()}${e.status.slice(1)}` as
                        "statusActive" | "statusDisabled" | "statusExpired" | "statusFull")}
                    </StatusMark>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-3">
                      <button
                        type="button"
                        onClick={() => kopieren(e)}
                        className="text-xs text-kb hover:underline flex items-center gap-1"
                      >
                        {kopiert === e.id ? <Check size={12} weight="bold" /> : <Copy size={12} weight="bold" />}
                        {kopiert === e.id ? t("copied") : t("copyCode")}
                      </button>
                      <button
                        type="button"
                        onClick={() => umschalten(e)}
                        className="text-xs text-kb hover:underline"
                      >
                        {e.active ? t("disable") : t("enable")}
                      </button>
                      <button
                        type="button"
                        onClick={() => setLoeschen(e)}
                        className="text-xs text-error hover:underline"
                      >
                        {t("delete")}
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <Modal
        open={!!loeschen}
        onClose={() => setLoeschen(null)}
        title={t("deleteTitle")}
        size="sm"
        footer={
          <>
            <button
              type="button"
              onClick={() => setLoeschen(null)}
              className="px-3 py-2 text-sm text-foreground-soft"
            >
              {t("cancel")}
            </button>
            <button
              type="button"
              onClick={() => loeschen && wirklichLoeschen(loeschen)}
              className="px-3 py-2 text-sm bg-error text-white rounded-md"
            >
              {t("deleteConfirm")}
            </button>
          </>
        }
      >
        <p className="text-sm text-foreground-soft">{t("deleteText", { n: loeschen?.used_count ?? 0 })}</p>
        <p className="mt-2 text-xs text-muted-soft">{t("deleteHint")}</p>
      </Modal>

      {dialogOffen && (
        <CreateAccessCodeDialog onClose={() => setDialogOffen(false)} onCreated={laden} />
      )}
    </div>
  );
}

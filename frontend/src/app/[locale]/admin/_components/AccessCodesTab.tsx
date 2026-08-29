"use client";

/** The access codes for the test rounds. */

import { useCallback, useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { Check } from "@phosphor-icons/react";
import Spinner from "@/components/ui/Spinner";
import Modal from "@/components/ui/Modal";
import StatusMark from "@/components/ui/StatusMark";
import type { StatusTone } from "@/lib/jobStatusDisplay";
import { copyTextFromPromise } from "@/lib/clipboard";
import CreateAccessCodeDialog from "./CreateAccessCodeDialog";

type Zustand = "active" | "disabled" | "expired" | "full";
type KontoZustand = "active" | "expired" | "disabled";

type Konto = {
  id: number;
  ldap_username: string;
  created_at: string;
  access_expires_at: string | null;
  active: boolean;
  status: KontoZustand;
};

const TON_KONTO: Record<KontoZustand, StatusTone> = {
  active: "brand",
  expired: "muted",
  disabled: "muted",
};

type Code = {
  id: number;
  code: string;
  label: string;
  role: string;
  custom_role_id: number | null;
  max_uses: number;
  used_count: number;
  valid_until: string;
  access_days: number | null;
  active: boolean;
  created_at: string;
  status: Zustand;
};

// The switch shows on or off, the word beside it shows why a code no longer works.
const FARBE: Record<Zustand, string> = {
  active: "var(--kb)",
  disabled: "var(--muted)",
  expired: "var(--muted)",
  full: "var(--warn-strong)",
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
  const [umschaltend, setUmschaltend] = useState<number | null>(null);
  const [kontenCode, setKontenCode] = useState<Code | null>(null);
  const [konten, setKonten] = useState<Konto[]>([]);
  const [kontenLoading, setKontenLoading] = useState(false);
  const [kontenError, setKontenError] = useState("");
  const [resettingId, setResettingId] = useState<number | null>(null);
  const [neuePasswoerter, setNeuePasswoerter] = useState<Record<number, string>>({});
  const [kopiertNutzer, setKopiertNutzer] = useState<number | null>(null);
  const [kopiertPasswort, setKopiertPasswort] = useState<number | null>(null);

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
    setUmschaltend(code.id);
    try {
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
    } finally {
      setUmschaltend(null);
    }
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

  function kontenOeffnen(code: Code) {
    setKontenCode(code);
    setKontenLoading(true);
    setKontenError("");
    fetch(`/api/admin/access-codes/${code.id}/users`, { credentials: "include" })
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error("load"))))
      .then((d) => setKonten(d.users ?? []))
      .catch(() => setKontenError(t("usersLoadError")))
      .finally(() => setKontenLoading(false));
  }

  function kontenSchliessen() {
    setKontenCode(null);
    setKonten([]);
    setKontenError("");
    setNeuePasswoerter({});
  }

  function kopierenNutzer(konto: Konto) {
    copyTextFromPromise(Promise.resolve(konto.ldap_username));
    setKopiertNutzer(konto.id);
    setTimeout(() => setKopiertNutzer(null), 1500);
  }

  function kopierenPasswort(konto: Konto, passwort: string) {
    copyTextFromPromise(Promise.resolve(passwort));
    setKopiertPasswort(konto.id);
    setTimeout(() => setKopiertPasswort(null), 1500);
  }

  async function passwortZuruecksetzen(konto: Konto) {
    setResettingId(konto.id);
    setKontenError("");
    try {
      const r = await fetch(`/api/admin/access-codes/users/${konto.id}/password`, {
        method: "POST",
        credentials: "include",
      });
      if (!r.ok) {
        setKontenError(t("resetError"));
        return;
      }
      const d = await r.json();
      setNeuePasswoerter((prev) => ({ ...prev, [konto.id]: d.password }));
    } finally {
      setResettingId(null);
    }
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
                  <td className="px-4 py-3 font-medium">
                    <button
                      type="button"
                      onClick={() => kontenOeffnen(e)}
                      title={t("usersTitle")}
                      className="text-foreground hover:text-kb hover:underline text-left rounded focus:outline-none focus:ring-2 focus:ring-kb"
                    >
                      {e.label}
                    </button>
                  </td>
                  <td className="px-4 py-3">
                    <button
                      type="button"
                      onClick={() => kopieren(e)}
                      aria-label={t("copyCode")}
                      className="font-mono text-foreground-soft hover:text-kb inline-flex items-center gap-1.5 rounded focus:outline-none focus:ring-2 focus:ring-kb"
                    >
                      {e.code}
                      {kopiert === e.id && <Check size={12} weight="bold" className="text-kb" />}
                    </button>
                  </td>
                  <td className="px-4 py-3 text-foreground-soft">{e.used_count} / {e.max_uses}</td>
                  <td className="px-4 py-3 text-foreground-soft">{datum(e.valid_until)}</td>
                  <td className="px-4 py-3 text-foreground-soft">
                    {e.access_days == null ? t("accessUnlimited") : t("accessDays", { n: e.access_days })}
                  </td>
                  <td
                    className="px-4 py-3 cursor-pointer"
                    onClick={() => umschaltend !== e.id && umschalten(e)}
                  >
                    <div className="flex items-center gap-2.5">
                      <button
                        type="button"
                        role="switch"
                        aria-checked={e.active}
                        aria-label={e.active ? t("disable") : t("enable")}
                        onClick={(ev) => { ev.stopPropagation(); umschalten(e); }}
                        disabled={umschaltend === e.id}
                        className="relative inline-flex h-5 w-9 flex-shrink-0 items-center rounded-full border-2 border-transparent transition-colors disabled:opacity-50 focus:outline-none focus:ring-2 focus:ring-offset-2 enabled:hover:border-kb"
                        style={{ backgroundColor: e.active ? "var(--kb)" : "var(--border)" }}
                      >
                        <span
                          className={`inline-block h-4 w-4 transform rounded-full bg-white shadow-sm transition-transform ${
                            e.active ? "translate-x-[1.125rem]" : "translate-x-0.5"
                          }`}
                        />
                      </button>
                      <span className="text-xs font-medium" style={{ color: FARBE[e.status] }}>
                        {t(`status${e.status[0].toUpperCase()}${e.status.slice(1)}` as
                          "statusActive" | "statusDisabled" | "statusExpired" | "statusFull")}
                      </span>
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <button
                      type="button"
                      onClick={() => setLoeschen(e)}
                      className="text-xs text-error hover:underline"
                    >
                      {t("delete")}
                    </button>
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
              className="px-4 py-2 text-sm border-2 border-border rounded-md hover:border-[var(--kb)] hover:text-[var(--kb)]"
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

      <Modal
        open={!!kontenCode}
        onClose={kontenSchliessen}
        title={kontenCode?.label}
        size="lg"
        footer={
          <button
            type="button"
            onClick={kontenSchliessen}
            className="px-4 py-2 text-sm border-2 border-border rounded-md hover:border-[var(--kb)] hover:text-[var(--kb)]"
          >
            {t("close")}
          </button>
        }
      >
        <div data-testid="access-code-users">
          <p className="font-mono text-xs text-muted-soft mb-3">{kontenCode?.code}</p>

          {kontenError && <p className="text-xs text-error mb-2">{kontenError}</p>}

          {kontenLoading ? (
            <Spinner className="flex justify-center py-8" />
          ) : konten.length === 0 ? (
            <p className="text-sm text-muted-soft text-center py-6">{t("usersEmpty")}</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm border border-border-soft rounded-xl overflow-hidden">
                <thead className="bg-surface text-xs text-muted uppercase">
                  <tr>
                    <th className="px-3 py-2 text-left">{t("colUser")}</th>
                    <th className="px-3 py-2 text-left">{t("colCreated")}</th>
                    <th className="px-3 py-2 text-left">{t("colExpires")}</th>
                    <th className="px-3 py-2 text-left">{t("colState")}</th>
                    <th className="px-3 py-2 text-left">{t("resetPassword")}</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border-soft bg-background">
                  {konten.map((k) => (
                    <tr key={k.id}>
                      <td className="px-3 py-2">
                        <button
                          type="button"
                          onClick={() => kopierenNutzer(k)}
                          aria-label={t("copyUser")}
                          className="font-mono text-foreground-soft hover:text-kb inline-flex items-center gap-1.5 rounded focus:outline-none focus:ring-2 focus:ring-kb"
                        >
                          {k.ldap_username}
                          {kopiertNutzer === k.id && <Check size={12} weight="bold" className="text-kb" />}
                        </button>
                      </td>
                      <td className="px-3 py-2 text-foreground-soft">{datum(k.created_at)}</td>
                      <td className="px-3 py-2 text-foreground-soft">
                        {k.access_expires_at == null ? t("accessUnlimited") : datum(k.access_expires_at)}
                      </td>
                      <td className="px-3 py-2">
                        <StatusMark tone={TON_KONTO[k.status]} className="text-xs">
                          {t(`state${k.status[0].toUpperCase()}${k.status.slice(1)}` as
                            "stateActive" | "stateExpired" | "stateDisabled")}
                        </StatusMark>
                      </td>
                      <td className="px-3 py-2">
                        {neuePasswoerter[k.id] ? (
                          <div className="flex flex-col gap-1">
                            <div className="flex items-center gap-1.5">
                              <span className="text-xs text-muted-soft">{t("newPassword")}:</span>
                              <button
                                type="button"
                                onClick={() => kopierenPasswort(k, neuePasswoerter[k.id])}
                                aria-label={t("copyPassword")}
                                className="font-mono text-foreground-soft hover:text-kb inline-flex items-center gap-1.5 rounded focus:outline-none focus:ring-2 focus:ring-kb"
                              >
                                {neuePasswoerter[k.id]}
                                {kopiertPasswort === k.id && <Check size={12} weight="bold" className="text-kb" />}
                              </button>
                            </div>
                            <span className="text-2xs text-muted-soft">{t("newPasswordOnce")}</span>
                          </div>
                        ) : (
                          <button
                            type="button"
                            data-testid="access-code-reset"
                            onClick={() => passwortZuruecksetzen(k)}
                            disabled={resettingId === k.id}
                            className="px-3 py-1.5 text-xs bg-kb text-white rounded-md disabled:opacity-50 whitespace-nowrap"
                          >
                            {resettingId === k.id ? t("resetting") : t("resetPassword")}
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </Modal>

      {dialogOffen && (
        <CreateAccessCodeDialog onClose={() => setDialogOffen(false)} onCreated={laden} />
      )}
    </div>
  );
}

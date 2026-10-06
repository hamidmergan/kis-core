"use client";

/** The access codes for the test rounds. */

import { useCallback, useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { Check, PencilSimple, QrCode, Trash } from "@phosphor-icons/react";
import Spinner from "@/components/ui/Spinner";
import Modal from "@/components/ui/Modal";
import IconButton from "@/components/ui/IconButton";
import StatusMark from "@/components/ui/StatusMark";
import type { StatusTone } from "@/lib/jobStatusDisplay";
import { copyTextFromPromise } from "@/lib/clipboard";
import { useSetting } from "../_settings/SettingsProvider";
import { NumberSetting } from "../_settings/fields";
import CreateAccessCodeDialog from "./CreateAccessCodeDialog";
import EditAccessCodeDialog from "./EditAccessCodeDialog";
import AccessCodeQr from "./AccessCodeQr";
import AccessCodeUsersDialog, { type KontenUmfang } from "./AccessCodeUsersDialog";

type Zustand = "active" | "disabled" | "expired" | "full";
type KontoZustand = "active" | "expired" | "disabled";

type Konto = {
  id: number;
  ldap_username: string;
  created_at: string;
  access_expires_at: string | null;
  active: boolean;
  status: KontoZustand;
  /** When the nightly sweep removes the account, null while nothing removes it. */
  delete_at: string | null;
};

type ModulBezug = "owner" | "enrolled";

type ModulEintrag = {
  workspace_id: number;
  title: string;
  relation: ModulBezug;
  since: string;
};

type NachrichtEintrag = {
  role: "user" | "assistant";
  content: string;
  created_at: string;
  failed: boolean;
  aborted: boolean;
  workspace_title: string;
};

const TON_BEZUG: Record<ModulBezug, StatusTone> = {
  owner: "brand",
  enrolled: "muted",
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
  access_hours: number | null;
  show_credentials: boolean;
  show_evaluation: boolean;
  workspaces: { id: number; title: string; owner_name: string | null }[];
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

function datumZeit(wert: string): string {
  return new Date(wert).toLocaleString("de-DE");
}

/** 24 Stunden und mehr zeigen sich als ganze Tage, alles darunter bleibt in Stunden. */
function zugangsdauer(stunden: number | null, t: ReturnType<typeof useTranslations>): string {
  if (stunden == null) return t("accessUnlimited");
  return stunden % 24 === 0 ? t("accessDays", { n: stunden / 24 }) : t("accessHours", { n: stunden });
}

export default function AccessCodesTab() {
  const t = useTranslations("admin.accessCodes");
  const tWs = useTranslations("admin.codeWorkspaces");
  const loeschfrist = useSetting<number>("access_account_delete_after_days", 30);
  const [codes, setCodes] = useState<Code[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [dialogOffen, setDialogOffen] = useState(false);
  const [kopiert, setKopiert] = useState<number | null>(null);
  const [bearbeiten, setBearbeiten] = useState<Code | null>(null);
  const [loeschen, setLoeschen] = useState<Code | null>(null);
  const [qrCode, setQrCode] = useState<Code | null>(null);
  const [umschaltend, setUmschaltend] = useState<number | null>(null);
  // undefined keeps the account list closed, null shows the accounts of every code.
  const [konten, setKonten] = useState<KontenUmfang | undefined>(undefined);
  const [aktivitaetKonto, setAktivitaetKonto] = useState<Konto | null>(null);
  const [aktivitaetModule, setAktivitaetModule] = useState<ModulEintrag[]>([]);
  const [aktivitaetNachrichten, setAktivitaetNachrichten] = useState<NachrichtEintrag[]>([]);
  const [aktivitaetLoading, setAktivitaetLoading] = useState(false);
  const [aktivitaetError, setAktivitaetError] = useState("");

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

  function aktivitaetOeffnen(konto: Konto) {
    setAktivitaetKonto(konto);
    setAktivitaetLoading(true);
    setAktivitaetError("");
    fetch(`/api/admin/access-codes/users/${konto.id}/activity`, { credentials: "include" })
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error("load"))))
      .then((d) => {
        setAktivitaetModule(d.workspaces ?? []);
        setAktivitaetNachrichten(d.messages ?? []);
      })
      .catch(() => setAktivitaetError(t("activityLoadError")))
      .finally(() => setAktivitaetLoading(false));
  }

  function aktivitaetSchliessen() {
    setAktivitaetKonto(null);
    setAktivitaetModule([]);
    setAktivitaetNachrichten([]);
    setAktivitaetError("");
  }

  const aktiv = codes.filter((e) => e.status === "active").length;

  return (
    <div className="space-y-3" data-testid="access-codes-tab">
      <NumberSetting
        field={loeschfrist}
        title={t("deleteAfterTitle")}
        hint={t("deleteAfterHint")}
        unit={t("deleteAfterUnit")}
        min={0}
        max={3650}
        outOfRange={t("deleteAfterOutOfRange")}
      />

      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="text-xs text-muted-soft">{t("summary", { n: codes.length, aktiv })}</span>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => setKonten(null)}
            data-testid="access-code-all-users"
            className="btn-cancel px-4 py-2 text-sm btn-secondary rounded-lg whitespace-nowrap"
          >
            {t("allUsersButton")}
          </button>
          <button
            type="button"
            onClick={() => setDialogOffen(true)}
            data-testid="access-code-create"
            className="px-3 py-2 text-sm btn-primary rounded-md transition-colors whitespace-nowrap"
          >
            {t("createButton")}
          </button>
        </div>
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
                      onClick={() => setKonten({ id: e.id, label: e.label, code: e.code })}
                      title={t("usersTitle")}
                      className="text-foreground hover:text-kb hover:underline text-left rounded focus:outline-none focus:ring-2 focus:ring-kb"
                    >
                      {e.label}
                    </button>
                    {e.workspaces.length > 0 && (
                      <p
                        className="text-xs text-muted-soft font-normal"
                        title={e.workspaces.map((w) => w.title).join(", ")}
                      >
                        {tWs("listCount", { n: e.workspaces.length })}
                      </p>
                    )}
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
                    {zugangsdauer(e.access_hours, t)}
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
                    <div className="flex items-center gap-1">
                      <IconButton
                        size="sm"
                        title={t("qrButton")}
                        aria-label={t("qrButton")}
                        onClick={() => setQrCode(e)}
                      >
                        <QrCode size={14} weight="bold" />
                      </IconButton>
                      <IconButton
                        size="sm"
                        title={t("edit")}
                        aria-label={t("edit")}
                        onClick={() => setBearbeiten(e)}
                      >
                        <PencilSimple size={14} weight="bold" />
                      </IconButton>
                      <IconButton
                        size="sm"
                        title={t("delete")}
                        aria-label={t("delete")}
                        onClick={() => setLoeschen(e)}
                      >
                        <Trash size={14} weight="bold" />
                      </IconButton>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <Modal
        open={!!qrCode}
        onClose={() => setQrCode(null)}
        title={qrCode?.label}
        size="sm"
      >
        {qrCode && <AccessCodeQr code={qrCode.code} label={qrCode.label} />}
      </Modal>

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

      {konten !== undefined && (
        <AccessCodeUsersDialog umfang={konten} onClose={() => setKonten(undefined)} />
      )}

      <Modal
        open={!!aktivitaetKonto}
        onClose={aktivitaetSchliessen}
        title={aktivitaetKonto?.ldap_username}
        size="xl"
        footer={
          <button
            type="button"
            onClick={aktivitaetSchliessen}
            className="px-4 py-2 text-sm border-2 border-border rounded-md hover:border-[var(--kb)] hover:text-[var(--kb)]"
          >
            {t("close")}
          </button>
        }
      >
        <div data-testid="access-code-activity-view" className="overflow-x-hidden">
          {aktivitaetError && <p className="text-xs text-error mb-2">{aktivitaetError}</p>}

          {aktivitaetLoading ? (
            <Spinner className="flex justify-center py-8" />
          ) : aktivitaetModule.length === 0 && aktivitaetNachrichten.length === 0 ? (
            <p className="text-sm text-muted-soft text-center py-6">{t("activityEmpty")}</p>
          ) : (
            <div className="space-y-5">
              <div>
                <h3 className="text-xs font-semibold uppercase text-muted mb-2">{t("activityModulesTitle")}</h3>
                {aktivitaetModule.length === 0 ? (
                  <p className="text-sm text-muted-soft">{t("activityModulesEmpty")}</p>
                ) : (
                  <ul className="space-y-1.5">
                    {aktivitaetModule.map((m) => (
                      <li key={m.workspace_id} className="flex items-center justify-between gap-2 text-sm">
                        <span className="truncate">{m.title}</span>
                        <div className="flex items-center gap-2 flex-shrink-0">
                          <StatusMark tone={TON_BEZUG[m.relation]} className="text-xs">
                            {t(m.relation === "owner" ? "activityRelationOwner" : "activityRelationJoined")}
                          </StatusMark>
                          <span className="text-xs text-muted-soft">{datum(m.since)}</span>
                        </div>
                      </li>
                    ))}
                  </ul>
                )}
              </div>

              <div>
                <h3 className="text-xs font-semibold uppercase text-muted mb-2">{t("activityMessagesTitle")}</h3>
                {aktivitaetNachrichten.length === 0 ? (
                  <p className="text-sm text-muted-soft">{t("activityMessagesEmpty")}</p>
                ) : (
                  <>
                    <p className="text-2xs text-muted-soft mb-2">{t("activityMessagesCapped")}</p>
                    <div className="space-y-3">
                      {aktivitaetNachrichten.map((n, i) => (
                        <div
                          key={i}
                          className={`flex flex-col gap-1 ${n.role === "user" ? "items-end" : "items-start"}`}
                        >
                          <div className="text-2xs text-muted-soft">
                            {n.workspace_title} · {datumZeit(n.created_at)}
                          </div>
                          <div
                            className="max-w-[85%] rounded-2xl px-3 py-2 text-sm whitespace-pre-wrap break-words"
                            style={
                              n.role === "user"
                                ? { backgroundColor: "var(--kb)", color: "white" }
                                : { backgroundColor: "var(--surface)", border: "1px solid var(--border)" }
                            }
                          >
                            {n.content || t("activityNoContent")}
                          </div>
                          {n.failed ? (
                            <StatusMark tone="error" className="text-xs">{t("activityFailed")}</StatusMark>
                          ) : n.aborted ? (
                            <StatusMark tone="warn" className="text-xs">{t("activityAborted")}</StatusMark>
                          ) : null}
                        </div>
                      ))}
                    </div>
                  </>
                )}
              </div>
            </div>
          )}
        </div>
      </Modal>

      {dialogOffen && (
        <CreateAccessCodeDialog onClose={() => setDialogOffen(false)} onCreated={laden} />
      )}

      {bearbeiten && (
        <EditAccessCodeDialog code={bearbeiten} onClose={() => setBearbeiten(null)} onSaved={laden} />
      )}
    </div>
  );
}

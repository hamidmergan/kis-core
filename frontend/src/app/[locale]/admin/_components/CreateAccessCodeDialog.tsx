"use client";

/** Create an access code: the form first, then the code to copy. */

import { useEffect, useMemo, useState } from "react";
import { useTranslations } from "next-intl";
import { Copy, Check } from "@phosphor-icons/react";
import Select from "@/components/ui/Select";
import Checkbox from "@/components/ui/Checkbox";
import { copyTextFromPromise } from "@/lib/clipboard";
import SeatsField from "./SeatsField";
import { choiceToSeats } from "./seats";
import AccessHoursField from "./AccessHoursField";
import { choiceToHours, hoursToChoice } from "./accessHours";
import ValidDaysField from "./ValidDaysField";
import { choiceToDays } from "./validDays";
import AccessCodeQr from "./AccessCodeQr";
import CodeWorkspacesField from "./CodeWorkspacesField";
import DialogHeading from "./DialogHeading";

type Props = {
  onClose: () => void;
  onCreated: () => void;
};

type CustomRole = { id: number; name: string };

type Erstellt = { code: string; label: string };

export default function CreateAccessCodeDialog({ onClose, onCreated }: Props) {
  const t = useTranslations("admin.createAccessCode");
  const tWs = useTranslations("admin.codeWorkspaces");
  const [label, setLabel] = useState("");
  const [role, setRole] = useState("staff");
  const [maxUses, setMaxUses] = useState("10");
  const [customUses, setCustomUses] = useState("");
  const [validDays, setValidDays] = useState("7");
  const [customDays, setCustomDays] = useState("");
  const startStunden = hoursToChoice(168);
  const [accessHours, setAccessHours] = useState(startStunden.choice);
  const [customHours, setCustomHours] = useState(startStunden.custom);
  const [showCredentials, setShowCredentials] = useState(true);
  const [showEvaluation, setShowEvaluation] = useState(false);
  const [workspaceIds, setWorkspaceIds] = useState<number[]>([]);
  const [customRoles, setCustomRoles] = useState<CustomRole[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [erstellt, setErstellt] = useState<Erstellt | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    fetch("/api/admin/roles", { credentials: "include" })
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        if (d?.custom_roles) setCustomRoles(d.custom_roles);
      })
      .catch(() => {});
  }, []);

  const roleOptions = useMemo(
    () => [
      { value: "staff", label: t("roleStaff") },
      { value: "user", label: t("roleUser") },
      ...customRoles.map((r) => ({ value: `custom:${r.id}`, label: r.name })),
    ],
    [t, customRoles],
  );

  const plaetze = choiceToSeats(maxUses, customUses);
  const stunden = choiceToHours(accessHours, customHours);
  const tage = choiceToDays(validDays, customDays);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (plaetze === null || stunden === undefined || tage === null) return;
    setSubmitting(true);
    setError(null);
    const custom = role.startsWith("custom:");
    try {
      const r = await fetch("/api/admin/access-codes", {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          label: label.trim(),
          max_uses: plaetze,
          valid_days: tage,
          access_hours: stunden,
          show_credentials: showCredentials,
          show_evaluation: showEvaluation,
          workspace_ids: workspaceIds,
          kis_role: custom ? "custom" : role,
          custom_role_id: custom ? Number(role.slice("custom:".length)) : null,
        }),
      });
      if (r.ok) {
        const resp = await r.json();
        setErstellt({ code: resp.code, label: resp.label });
        onCreated();
      } else {
        const body = await r.json().catch(() => ({}));
        setError(typeof body?.detail === "string" ? body.detail : t("errorGeneric"));
      }
    } catch {
      setError(t("errorGeneric"));
    } finally {
      setSubmitting(false);
    }
  }

  function copyCode() {
    if (!erstellt) return;
    copyTextFromPromise(Promise.resolve(erstellt.code));
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="bg-background border border-border rounded-xl shadow-xl w-full max-w-md max-h-[90dvh] overflow-y-auto p-6 space-y-4">
        {erstellt ? (
          <>
            <DialogHeading onClose={onClose}>{t("createdTitle")}</DialogHeading>
            <p className="text-sm text-muted-soft">{t("createdHint")}</p>

            <div className="flex items-center gap-2">
              <code
                data-testid="access-code-value"
                className="flex-1 min-w-0 truncate font-mono text-lg bg-surface border border-border rounded-md px-3 py-2 select-all"
              >
                {erstellt.code}
              </code>
              <button
                type="button"
                onClick={copyCode}
                className="px-3 py-2 text-sm border-2 border-border rounded-md hover:border-[var(--kb)] hover:text-[var(--kb)] flex items-center gap-1 whitespace-nowrap"
              >
                {copied ? <Check size={16} weight="bold" /> : <Copy size={16} weight="bold" />}
                {copied ? t("copied") : t("copy")}
              </button>
            </div>

            <AccessCodeQr code={erstellt.code} label={erstellt.label} />

            <div className="flex justify-end pt-2">
              <button
                type="button"
                onClick={onClose}
                className="px-4 py-2 text-sm btn-primary rounded-md transition-colors"
              >
                {t("close")}
              </button>
            </div>
          </>
        ) : (
          <form onSubmit={submit} className="space-y-3">
            <DialogHeading onClose={onClose} disabled={submitting}>{t("title")}</DialogHeading>

            <div className="space-y-1">
              <label className="text-xs uppercase tracking-wide text-muted" htmlFor="access-code-label">
                {t("label")}
              </label>
              <input
                id="access-code-label"
                type="text"
                required
                autoFocus
                value={label}
                onChange={(e) => setLabel(e.target.value)}
                className="w-full text-sm border border-border rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-kb"
              />
              <p className="text-xs text-muted-soft">{t("labelHint")}</p>
            </div>

            <SeatsField
              choice={maxUses}
              custom={customUses}
              onChoice={setMaxUses}
              onCustom={setCustomUses}
            />

            <ValidDaysField
              choice={validDays}
              custom={customDays}
              onChoice={setValidDays}
              onCustom={setCustomDays}
            />

            <AccessHoursField
              choice={accessHours}
              custom={customHours}
              onChoice={setAccessHours}
              onCustom={setCustomHours}
            />

            <div className="space-y-1">
              <label className="text-xs uppercase tracking-wide text-muted">{t("role")}</label>
              <Select value={role} onChange={setRole} options={roleOptions} className="w-full" />
            </div>

            <CodeWorkspacesField value={workspaceIds} onChange={setWorkspaceIds} hint={tWs("hintCreate")} />

            <Checkbox
              checked={showCredentials}
              onChange={setShowCredentials}
              label={t("showCredentials")}
            />
            <p className="text-xs text-muted-soft -mt-2">{t("showCredentialsHint")}</p>

            <Checkbox
              checked={showEvaluation}
              onChange={setShowEvaluation}
              label={t("showEvaluation")}
            />
            <p className="text-xs text-muted-soft -mt-2">{t("showEvaluationHint")}</p>

            {error && <p className="text-sm text-error">{error}</p>}

            <div className="flex justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={onClose}
                disabled={submitting}
                className="px-4 py-2 text-sm border-2 border-border rounded-md hover:border-[var(--kb)] hover:text-[var(--kb)]"
              >
                {t("cancel")}
              </button>
              <button
                type="submit"
                data-testid="access-code-submit"
                disabled={submitting || !label.trim() || plaetze === null || stunden === undefined || tage === null}
                className="px-4 py-2 text-sm btn-primary rounded-md transition-colors disabled:opacity-60"
              >
                {submitting ? t("submitting") : t("submit")}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}

"use client";

/** Edit an access code: everything but the code itself. */

import { useEffect, useMemo, useState } from "react";
import { useTranslations } from "next-intl";
import Select from "@/components/ui/Select";
import Checkbox from "@/components/ui/Checkbox";
import SeatsField from "./SeatsField";
import { choiceToSeats, seatsToChoice } from "./seats";
import AccessHoursField from "./AccessHoursField";
import { choiceToHours, hoursToChoice } from "./accessHours";

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
};

type Props = {
  code: Code;
  onClose: () => void;
  onSaved: () => void;
};

type CustomRole = { id: number; name: string };

const VALID_DAYS = [7, 14, 30, 60];

function verbleibendeTage(validUntil: string): number {
  const tage = Math.ceil((new Date(validUntil).getTime() - Date.now()) / 86_400_000);
  return Math.min(60, Math.max(1, tage));
}

export default function EditAccessCodeDialog({ code, onClose, onSaved }: Props) {
  const t = useTranslations("admin.editAccessCode");
  const tCreate = useTranslations("admin.createAccessCode");
  const [label, setLabel] = useState(code.label);
  const [role, setRole] = useState(code.custom_role_id ? `custom:${code.custom_role_id}` : code.role);
  const startPlaetze = seatsToChoice(code.max_uses);
  const [maxUses, setMaxUses] = useState(startPlaetze.choice);
  const [customUses, setCustomUses] = useState(startPlaetze.custom);
  const [validDays, setValidDays] = useState(String(verbleibendeTage(code.valid_until)));
  const startStunden = hoursToChoice(code.access_hours);
  const [accessHours, setAccessHours] = useState(startStunden.choice);
  const [customHours, setCustomHours] = useState(startStunden.custom);
  const [showCredentials, setShowCredentials] = useState(code.show_credentials);
  const [showEvaluation, setShowEvaluation] = useState(code.show_evaluation);
  const [customRoles, setCustomRoles] = useState<CustomRole[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

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
      { value: "staff", label: tCreate("roleStaff") },
      { value: "user", label: tCreate("roleUser") },
      ...customRoles.map((r) => ({ value: `custom:${r.id}`, label: r.name })),
    ],
    [tCreate, customRoles],
  );

  const validDaysOptions = useMemo(() => {
    const werte = VALID_DAYS.includes(Number(validDays)) ? VALID_DAYS : [Number(validDays), ...VALID_DAYS];
    return werte.map((n) => ({ value: String(n), label: tCreate("days", { n }) }));
  }, [tCreate, validDays]);

  const plaetze = choiceToSeats(maxUses, customUses);
  const stunden = choiceToHours(accessHours, customHours);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (plaetze === null || stunden === undefined) return;
    setSubmitting(true);
    setError(null);
    const custom = role.startsWith("custom:");
    try {
      const r = await fetch(`/api/admin/access-codes/${code.id}`, {
        method: "PATCH",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          label: label.trim(),
          max_uses: plaetze,
          valid_days: Number(validDays),
          access_hours: stunden,
          show_credentials: showCredentials,
          show_evaluation: showEvaluation,
          kis_role: custom ? "custom" : role,
          custom_role_id: custom ? Number(role.slice("custom:".length)) : null,
        }),
      });
      if (r.ok) {
        onSaved();
        onClose();
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

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="bg-background border border-border rounded-xl shadow-xl w-full max-w-md p-6 space-y-4">
        <form onSubmit={submit} className="space-y-3">
          <h2 className="text-lg font-semibold">{t("title")}</h2>

          <div className="space-y-1">
            <span className="text-xs uppercase tracking-wide text-muted">{t("code")}</span>
            <p className="font-mono text-sm text-foreground-soft">{code.code}</p>
          </div>

          <div className="space-y-1">
            <label className="text-xs uppercase tracking-wide text-muted" htmlFor="edit-access-code-label">
              {tCreate("label")}
            </label>
            <input
              id="edit-access-code-label"
              type="text"
              required
              autoFocus
              value={label}
              onChange={(e) => setLabel(e.target.value)}
              className="w-full text-sm border border-border rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-kb"
            />
          </div>

          <SeatsField
            choice={maxUses}
            custom={customUses}
            onChoice={setMaxUses}
            onCustom={setCustomUses}
          />

          <div className="space-y-1">
            <label className="text-xs uppercase tracking-wide text-muted">{tCreate("validDays")}</label>
            <Select value={validDays} onChange={setValidDays} options={validDaysOptions} className="w-full" />
          </div>

          <AccessHoursField
            choice={accessHours}
            custom={customHours}
            onChoice={setAccessHours}
            onCustom={setCustomHours}
          />

          <div className="space-y-1">
            <label className="text-xs uppercase tracking-wide text-muted">{tCreate("role")}</label>
            <Select value={role} onChange={setRole} options={roleOptions} className="w-full" />
          </div>

          <Checkbox
            checked={showCredentials}
            onChange={setShowCredentials}
            label={tCreate("showCredentials")}
          />
          <p className="text-xs text-muted-soft -mt-2">{tCreate("showCredentialsHint")}</p>

          <Checkbox
            checked={showEvaluation}
            onChange={setShowEvaluation}
            label={tCreate("showEvaluation")}
          />
          <p className="text-xs text-muted-soft -mt-2">{tCreate("showEvaluationHint")}</p>

          {error && <p className="text-sm text-error">{error}</p>}

          <div className="flex justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={onClose}
              disabled={submitting}
              className="px-4 py-2 text-sm border-2 border-border rounded-md hover:border-[var(--kb)] hover:text-[var(--kb)]"
            >
              {tCreate("cancel")}
            </button>
            <button
              type="submit"
              data-testid="access-code-edit-submit"
              disabled={submitting || !label.trim() || plaetze === null || stunden === undefined}
              className="px-4 py-2 text-sm btn-primary rounded-md transition-colors disabled:opacity-60"
            >
              {submitting ? t("submitting") : t("submit")}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

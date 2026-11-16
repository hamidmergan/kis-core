"use client";

/** State and the shared fields of the create and the edit dialog of an access code. */

import { useState } from "react";
import { useTranslations } from "next-intl";
import Select from "@/components/ui/Select";
import Checkbox from "@/components/ui/Checkbox";
import SeatsField from "./SeatsField";
import { choiceToSeats } from "./seats";
import AccessHoursField from "./AccessHoursField";
import { choiceToHours } from "./accessHours";
import ValidDaysField from "./ValidDaysField";
import { choiceToDays } from "./validDays";
import { roleToPayload, useRoleOptions } from "./useRoleOptions";

type Choice = { choice: string; custom: string };

type Start = {
  label: string;
  role: string;
  seats: Choice;
  days: Choice;
  hours: Choice;
  showCredentials: boolean;
  showEvaluation: boolean;
  workspaceIds: number[];
};

export function useAccessCodeForm(start: Start) {
  const t = useTranslations("admin.createAccessCode");
  const [label, setLabel] = useState(start.label);
  const [role, setRole] = useState(start.role);
  const [maxUses, setMaxUses] = useState(start.seats.choice);
  const [customUses, setCustomUses] = useState(start.seats.custom);
  const [validDays, setValidDays] = useState(start.days.choice);
  const [customDays, setCustomDays] = useState(start.days.custom);
  const [accessHours, setAccessHours] = useState(start.hours.choice);
  const [customHours, setCustomHours] = useState(start.hours.custom);
  const [showCredentials, setShowCredentials] = useState(start.showCredentials);
  const [showEvaluation, setShowEvaluation] = useState(start.showEvaluation);
  const [workspaceIds, setWorkspaceIds] = useState<number[]>(start.workspaceIds);
  const roleOptions = useRoleOptions(t("roleStaff"), t("roleUser"));

  const plaetze = choiceToSeats(maxUses, customUses);
  const stunden = choiceToHours(accessHours, customHours);
  const tage = choiceToDays(validDays, customDays);
  const valid = plaetze !== null && stunden !== undefined && tage !== null;

  // The request body, null while a number field holds something unusable.
  const payload = valid
    ? {
        label: label.trim(),
        max_uses: plaetze,
        valid_days: tage,
        access_hours: stunden,
        show_credentials: showCredentials,
        show_evaluation: showEvaluation,
        workspace_ids: workspaceIds,
        ...roleToPayload(role),
      }
    : null;

  return {
    label, setLabel, role, setRole, roleOptions,
    maxUses, setMaxUses, customUses, setCustomUses,
    validDays, setValidDays, customDays, setCustomDays,
    accessHours, setAccessHours, customHours, setCustomHours,
    showCredentials, setShowCredentials, showEvaluation, setShowEvaluation,
    workspaceIds, setWorkspaceIds,
    payload,
    canSubmit: !!label.trim() && valid,
  };
}

type Form = ReturnType<typeof useAccessCodeForm>;

/** Seats, validity, access time and role. */
export function AccessCodeLimits({ form }: { form: Form }) {
  const t = useTranslations("admin.createAccessCode");
  return (
    <>
      <SeatsField
        choice={form.maxUses}
        custom={form.customUses}
        onChoice={form.setMaxUses}
        onCustom={form.setCustomUses}
      />

      <ValidDaysField
        choice={form.validDays}
        custom={form.customDays}
        onChoice={form.setValidDays}
        onCustom={form.setCustomDays}
      />

      <AccessHoursField
        choice={form.accessHours}
        custom={form.customHours}
        onChoice={form.setAccessHours}
        onCustom={form.setCustomHours}
      />

      <div className="space-y-1">
        <label className="text-xs uppercase tracking-wide text-muted">{t("role")}</label>
        <Select value={form.role} onChange={form.setRole} options={form.roleOptions} className="w-full" />
      </div>
    </>
  );
}

/** The two switches for the credentials note and the evaluation. */
export function AccessCodeFlags({ form }: { form: Form }) {
  const t = useTranslations("admin.createAccessCode");
  return (
    <>
      <Checkbox
        checked={form.showCredentials}
        onChange={form.setShowCredentials}
        label={t("showCredentials")}
      />
      <p className="text-xs text-muted-soft -mt-2">{t("showCredentialsHint")}</p>

      <Checkbox
        checked={form.showEvaluation}
        onChange={form.setShowEvaluation}
        label={t("showEvaluation")}
      />
      <p className="text-xs text-muted-soft -mt-2">{t("showEvaluationHint")}</p>
    </>
  );
}

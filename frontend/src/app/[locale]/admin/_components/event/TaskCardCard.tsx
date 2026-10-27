"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { SettingCard, Switch } from "@/app/[locale]/admin/_settings/fields";
import Checkbox from "@/components/ui/Checkbox";
import Select from "@/components/ui/Select";
import { useEventAdminState, useEventConfig } from "@/lib/event/adminStore";
import { eventApi } from "@/lib/event/api";
import type { TaskCardConfig } from "@/lib/event/types";
import { INPUT, Labeled } from "./fields";

/** Switch, period, access code and workspace of the task card on the services page. */
export default function TaskCardCard() {
  const t = useTranslations("eventAdmin.tasks");
  const [config, update] = useEventConfig();
  const card = config.taskCard;
  const set = (patch: Partial<TaskCardConfig>) => update((c) => ({ ...c, taskCard: { ...c.taskCard, ...patch } }));
  const [workspaces, setWorkspaces] = useState<{ uuid: string; title: string }[]>([]);

  // The server only lists the saved code's workspaces, so the list follows each finished save.
  const { status } = useEventAdminState();
  useEffect(() => {
    if (status === "saving") return;
    let alive = true;
    eventApi
      .adminTaskWorkspaces()
      .then((r) => alive && setWorkspaces(r.workspaces))
      .catch(() => alive && setWorkspaces([]));
    return () => {
      alive = false;
    };
  }, [status]);

  const known = workspaces.some((w) => w.uuid === card.workspace);
  const options = [
    { value: "", label: t("workspaceNone") },
    ...workspaces.map((w) => ({ value: w.uuid, label: w.title })),
    ...(card.workspace && !known ? [{ value: card.workspace, label: t("workspaceUnknown") }] : []),
  ];

  return (
    <SettingCard
      title={t("title")}
      description={card.enabled ? t("active") : t("disabled")}
      control={<Switch checked={card.enabled} onChange={(enabled) => set({ enabled })} label={t("toggleAria")} />}
    >
      <div className="mt-4 flex flex-col gap-3" data-testid="task-card-admin">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
          <Labeled label={t("from")}>
            <input type="date" value={card.from} onChange={(e) => set({ from: e.target.value })} className={`${INPUT} min-w-0`} />
          </Labeled>
          <Labeled label={t("until")}>
            <input type="date" value={card.until} onChange={(e) => set({ until: e.target.value })} className={`${INPUT} min-w-0`} />
          </Labeled>
        </div>
        <Checkbox
          checked={card.ignoreWindow}
          onChange={(ignoreWindow) => set({ ignoreWindow })}
          label={t("ignoreWindow")}
          labelClassName="text-sm"
        />
        <Labeled label={t("accessCode")}>
          <input
            type="text"
            value={card.accessCode}
            onChange={(e) => set({ accessCode: e.target.value })}
            className={`${INPUT} font-mono`}
          />
        </Labeled>
        <p className="text-xs text-muted -mt-1">{t("accessCodeHint")}</p>
        <Labeled label={t("workspace")}>
          <Select value={card.workspace} onChange={(workspace) => set({ workspace })} options={options} ariaLabel={t("workspace")} />
        </Labeled>
        <p className="text-xs text-muted -mt-1">{workspaces.length ? t("workspaceHint") : t("workspaceEmpty")}</p>
      </div>
    </SettingCard>
  );
}

"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { SettingCard, Switch } from "@/app/[locale]/admin/_settings/fields";
import { newUniqueCode } from "@/lib/event/codes";
import ConfirmDialog from "@/components/event/ConfirmDialog";
import { useEventConfig } from "@/lib/event/adminStore";
import type { Station } from "@/lib/event/types";
import StationEditor from "./StationEditor";
import { BTN_PRIMARY } from "./fields";

/** The first free id in the form stand-n, readable in the QR link. */
export function nextId(prefix: string, taken: { id: string }[]): string {
  const ids = new Set(taken.map((x) => x.id));
  let n = taken.length + 1;
  while (ids.has(`${prefix}-${n}`)) n++;
  return `${prefix}-${n}`;
}

const EMPTY = { de: "", en: "" };

export default function StationsCard({ onQr }: { onQr: (id: string) => void }) {
  const t = useTranslations("eventAdmin.stations");
  const [config, update] = useEventConfig();
  const [removeId, setRemoveId] = useState<string | null>(null);
  const [freshId, setFreshId] = useState<string | null>(null);
  const stations = config.stations;

  const setStations = (fn: (s: Station[]) => Station[]) => update((c) => ({ ...c, stations: fn(c.stations) }));

  const add = () => {
    const id = nextId("stand", stations);
    setFreshId(id);
    update((c) => ({
      ...c,
      stations: [
        ...c.stations,
        { id, code: newUniqueCode(c.stations.map((x) => x.code)), icon: "star", name: EMPTY, blurb: EMPTY, francis: EMPTY },
      ],
    }));
  };
  const move = (index: number, delta: -1 | 1) =>
    setStations((s) => {
      const next = [...s];
      const [item] = next.splice(index, 1);
      next.splice(index + delta, 0, item);
      return next;
    });
  const remove = () => {
    if (removeId) setStations((s) => s.filter((x) => x.id !== removeId));
    setRemoveId(null);
  };

  return (
    <SettingCard
      title={t("title")}
      description={t("description")}
      control={
        <>
          <button type="button" onClick={add} className={BTN_PRIMARY} data-testid="station-add">
            {t("add")}
          </button>
        </>
      }
    >
      <div className="mt-4 flex items-center justify-between gap-4 rounded-lg border border-border-soft bg-surface px-3 py-2.5">
        <span className="text-sm text-foreground-soft">{t("hideCode")}</span>
        <Switch
          checked={config.hideCodeOnPosters}
          onChange={(hideCodeOnPosters) => update((c) => ({ ...c, hideCodeOnPosters }))}
          label={t("hideCodeAria")}
        />
      </div>
      <div className="mt-4 flex flex-col gap-3" data-testid="station-list">
        {stations.length === 0 && <p className="text-sm text-muted">{t("empty")}</p>}
        {stations.map((station, i) => (
          <StationEditor
            key={station.id}
            station={station}
            first={i === 0}
            last={i === stations.length - 1}
            defaultOpen={station.id === freshId}
            onChange={(next) => setStations((s) => s.map((x) => (x.id === station.id ? next : x)))}
            takenCodes={stations.filter((x) => x.id !== station.id).map((x) => x.code)}
            onMove={(delta) => move(i, delta)}
            onRemove={() => setRemoveId(station.id)}
            onQr={() => onQr(station.id)}
          />
        ))}
      </div>
      {removeId && (
        <ConfirmDialog
          title={t("removeTitle")}
          text={t("removeText")}
          confirmLabel={t("remove")}
          onConfirm={remove}
          onCancel={() => setRemoveId(null)}
          testId="station-remove-confirm"
        />
      )}
    </SettingCard>
  );
}

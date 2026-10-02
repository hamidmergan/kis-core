"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { SettingCard } from "@/app/[locale]/admin/_settings/fields";
import { newUniqueCode } from "../../../_lib/masterCode";
import ConfirmDialog from "../../../_components/ConfirmDialog";
import { useMockup } from "../../../_lib/store";
import type { Station } from "../../../_lib/types";
import StationEditor from "./StationEditor";
import { BTN_PRIMARY, BTN_SECONDARY } from "./fields";

/** The first free id in the form stand-n, readable in the QR link. */
export function nextId(prefix: string, taken: { id: string }[]): string {
  const ids = new Set(taken.map((x) => x.id));
  let n = taken.length + 1;
  while (ids.has(`${prefix}-${n}`)) n++;
  return `${prefix}-${n}`;
}

const EMPTY = { de: "", en: "" };

export default function StationsCard({ onQr, onPrintAll }: { onQr: (id: string) => void; onPrintAll: () => void }) {
  const t = useTranslations("mockup.admin.stations");
  const tp = useTranslations("mockup.admin.poster");
  const [config, update] = useMockup("config");
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
        { id, code: newUniqueCode([c.masterCode, ...c.stations.map((x) => x.code)]), icon: "star", name: EMPTY, blurb: EMPTY, francis: EMPTY },
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
          <button type="button" onClick={onPrintAll} disabled={!stations.length} className={BTN_SECONDARY} data-testid="print-all">
            {tp("all")}
          </button>
          <button type="button" onClick={add} className={BTN_PRIMARY} data-testid="station-add">
            {t("add")}
          </button>
        </>
      }
    >
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
            takenCodes={[config.masterCode, ...stations.filter((x) => x.id !== station.id).map((x) => x.code)]}
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

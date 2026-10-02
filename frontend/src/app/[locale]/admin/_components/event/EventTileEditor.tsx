"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { Trash } from "@phosphor-icons/react";
import CollapsibleCard from "@/components/ui/CollapsibleCard";
import IconButton from "@/components/ui/IconButton";
import Select from "@/components/ui/Select";
import { SettingCard, Switch } from "@/app/[locale]/admin/_settings/fields";
import ConfirmDialog from "@/components/event/ConfirmDialog";
import { EVENT_ICONS } from "@/lib/event/icons";
import { useEventConfig } from "@/lib/event/adminStore";
import { useText2 } from "@/lib/event/useText2";
import { MAX_TILES, type EventTile, type TileTarget } from "@/lib/event/types";
import { nextId } from "./StationsCard";
import { BTN_PRIMARY, INPUT, IconSelect, Labeled, TextPair } from "./fields";

type Kind = TileTarget["kind"];
const KINDS: Kind[] = ["stamp", "info", "internal", "directLogin"];
const EMPTY = { de: "", en: "" };

function targetFor(kind: Kind): TileTarget {
  if (kind === "internal") return { kind, path: "" };
  if (kind === "directLogin") return { kind, accessCode: "" };
  return { kind };
}

function TileEditor({ tile, defaultOpen, onChange, onRemove }: {
  tile: EventTile;
  defaultOpen: boolean;
  onChange: (next: EventTile) => void;
  onRemove: () => void;
}) {
  const t = useTranslations("eventAdmin.event");
  const tt = useTranslations("eventBlock.target");
  const text = useText2();
  const Icon = EVENT_ICONS[tile.icon];
  const target = tile.target;
  const [removeOpen, setRemoveOpen] = useState(false);
  return (
    <div className="flex items-start gap-2">
      <div className="flex-1 min-w-0">
        <CollapsibleCard
          defaultOpen={defaultOpen}
          title={
            <span className="inline-flex items-center gap-2">
              <Icon size={16} weight="bold" aria-hidden="true" className="text-kb" />
              {text(tile.title) || t("tileUntitled")}
            </span>
          }
          description={tt(target.kind)}
        >
          <div className="flex flex-col gap-3" data-testid="tile-editor">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              <IconSelect label={t("tileIcon")} value={tile.icon} onChange={(icon) => onChange({ ...tile, icon })} />
              <Labeled label={t("tileTarget")}>
                <Select<Kind>
                  value={target.kind}
                  onChange={(kind) => onChange({ ...tile, target: targetFor(kind) })}
                  options={KINDS.map((k) => ({ value: k, label: tt(k) }))}
                  ariaLabel={t("tileTarget")}
                />
              </Labeled>
            </div>
            {target.kind === "internal" && (
              <Labeled label={t("internalPath")}>
                <input type="text" value={target.path} onChange={(e) => onChange({ ...tile, target: { kind: "internal", path: e.target.value } })} className={INPUT} />
              </Labeled>
            )}
            {target.kind === "directLogin" && (
              <Labeled label={t("accessCode")}>
                <input type="text" value={target.accessCode} onChange={(e) => onChange({ ...tile, target: { kind: "directLogin", accessCode: e.target.value } })} className={`${INPUT} font-mono`} />
              </Labeled>
            )}
            <div className="flex items-center justify-between gap-4 rounded-lg border border-border-soft bg-surface px-3 py-2.5">
              <span className="text-sm text-foreground-soft">{tile.active ? t("tileActive") : t("tileLocked")}</span>
              <Switch checked={tile.active} onChange={(active) => onChange({ ...tile, active })} label={t("tileActiveAria")} />
            </div>
            <Labeled label={t("tileAvailableFrom")}>
              <input type="date" value={tile.availableFrom} onChange={(e) => onChange({ ...tile, availableFrom: e.target.value })} className={`${INPUT} min-w-0`} />
            </Labeled>
            <TextPair label={t("tileTitle")} value={tile.title} onChange={(title) => onChange({ ...tile, title })} />
            <TextPair label={t("tileBody")} value={tile.body} rows={2} onChange={(body) => onChange({ ...tile, body })} />
            <TextPair label={t("tileButton")} value={tile.button} onChange={(button) => onChange({ ...tile, button })} />
          </div>
        </CollapsibleCard>
      </div>
      <div className="pt-4">
        <IconButton size="sm" aria-label={t("removeTile")} title={t("removeTile")} onClick={() => setRemoveOpen(true)} data-testid="tile-remove">
          <Trash size={12} weight="bold" aria-hidden="true" />
        </IconButton>
      </div>
      {removeOpen && (
        <ConfirmDialog
          title={t("removeTileTitle")}
          text={t("removeTileText")}
          confirmLabel={t("removeTile")}
          onConfirm={onRemove}
          onCancel={() => setRemoveOpen(false)}
          testId="tile-remove-confirm"
        />
      )}
    </div>
  );
}

/** Up to four tiles, each a collapsible form, the add button stops at the limit. */
export default function EventTileEditor() {
  const t = useTranslations("eventAdmin.event");
  const [config, update] = useEventConfig();
  const [freshId, setFreshId] = useState<string | null>(null);
  const tiles = config.eventBlock.tiles;
  const full = tiles.length >= MAX_TILES;
  const setTiles = (fn: (ts: EventTile[]) => EventTile[]) =>
    update((c) => ({ ...c, eventBlock: { ...c.eventBlock, tiles: fn(c.eventBlock.tiles) } }));

  const add = () => {
    const id = nextId("kachel", tiles);
    setFreshId(id);
    setTiles((ts) => [...ts, { id, icon: "star", title: EMPTY, body: EMPTY, button: EMPTY, target: { kind: "info" }, active: false, availableFrom: "" }]);
  };

  return (
    <SettingCard
      title={t("tiles")}
      description={full ? t("maxTiles") : undefined}
      control={
        <button type="button" onClick={add} disabled={full} className={`${BTN_PRIMARY} disabled:opacity-50`} data-testid="tile-add">
          {t("addTile")}
        </button>
      }
    >
      <div className="mt-4 flex flex-col gap-3" data-testid="tile-list">
        {tiles.length === 0 && <p className="text-sm text-muted">{t("noTiles")}</p>}
        {tiles.map((tile) => (
          <TileEditor
            key={tile.id}
            tile={tile}
            defaultOpen={tile.id === freshId}
            onChange={(next) => setTiles((ts) => ts.map((x) => (x.id === tile.id ? next : x)))}
            onRemove={() => setTiles((ts) => ts.filter((x) => x.id !== tile.id))}
          />
        ))}
      </div>
    </SettingCard>
  );
}

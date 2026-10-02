"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { ArrowDown, ArrowUp, QrCode } from "@phosphor-icons/react";
import CollapsibleCard from "@/components/ui/CollapsibleCard";
import IconButton from "@/components/ui/IconButton";
import ConfirmDialog from "../../../_components/ConfirmDialog";
import { MOCKUP_ICONS } from "../../../_lib/icons";
import { newUniqueCode } from "../../../_lib/masterCode";
import { useText2 } from "../../../_lib/useText2";
import type { Station } from "../../../_lib/types";
import { BTN_SECONDARY, IconSelect, TextPair } from "./fields";

interface Props {
  station: Station;
  first: boolean;
  last: boolean;
  defaultOpen?: boolean;
  onChange: (next: Station) => void;
  onMove: (delta: -1 | 1) => void;
  onRemove: () => void;
  onQr: () => void;
  /** Codes of the master and all other stands, a new code must avoid them. */
  takenCodes: string[];
}

/** One stand as a collapsible form, the arrows beside it change the order. */
export default function StationEditor({ station, first, last, defaultOpen, onChange, onMove, onRemove, onQr, takenCodes }: Props) {
  const t = useTranslations("mockup.admin.stations");
  const text = useText2();
  const Icon = MOCKUP_ICONS[station.icon];
  const [rerollOpen, setRerollOpen] = useState(false);
  return (
    <div className="flex items-start gap-2" data-testid="station-editor">
      <div className="flex-1 min-w-0">
        <CollapsibleCard
          defaultOpen={defaultOpen}
          title={
            <span className="inline-flex items-center gap-2">
              <Icon size={16} weight="bold" aria-hidden="true" className="text-kb" />
              {text(station.name) || t("untitled")}
            </span>
          }
          description={text(station.blurb) || undefined}
        >
          <div className="flex flex-col gap-3">
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={onQr}
                className={`${BTN_SECONDARY} inline-flex items-center gap-2`}
                data-testid="station-qr"
              >
                <QrCode size={16} weight="bold" aria-hidden="true" />
                {t("qr")}
              </button>
              <button type="button" onClick={onRemove} className={BTN_SECONDARY} data-testid="station-remove">
                {t("remove")}
              </button>
            </div>
            <div className="flex flex-wrap items-center gap-3" data-testid="station-code-row">
              <span className="text-sm text-foreground-soft">{t("code")}</span>
              <span className="font-mono text-lg font-semibold tracking-widest text-foreground" data-testid="station-code">
                {station.code}
              </span>
              <button
                type="button"
                onClick={() => setRerollOpen(true)}
                className={BTN_SECONDARY}
                data-testid="station-code-reroll"
              >
                {t("codeReroll")}
              </button>
            </div>
            <IconSelect label={t("icon")} value={station.icon} onChange={(icon) => onChange({ ...station, icon })} />
            <TextPair label={t("name")} value={station.name} onChange={(name) => onChange({ ...station, name })} />
            <TextPair label={t("blurb")} value={station.blurb} onChange={(blurb) => onChange({ ...station, blurb })} />
            <TextPair
              label={t("francis")}
              value={station.francis}
              rows={2}
              onChange={(francis) => onChange({ ...station, francis })}
            />
          </div>
        </CollapsibleCard>
      </div>
      <div className="flex flex-col gap-1 pt-4">
        <IconButton size="sm" aria-label={t("up")} title={t("up")} disabled={first} onClick={() => onMove(-1)} className="disabled:opacity-40">
          <ArrowUp size={12} weight="bold" aria-hidden="true" />
        </IconButton>
        <IconButton size="sm" aria-label={t("down")} title={t("down")} disabled={last} onClick={() => onMove(1)} className="disabled:opacity-40">
          <ArrowDown size={12} weight="bold" aria-hidden="true" />
        </IconButton>
      </div>
      {rerollOpen && (
        <ConfirmDialog
          title={t("codeRerollTitle")}
          text={t("codeRerollText")}
          confirmLabel={t("codeReroll")}
          onConfirm={() => {
            onChange({ ...station, code: newUniqueCode(takenCodes) });
            setRerollOpen(false);
          }}
          onCancel={() => setRerollOpen(false)}
          testId="station-code-reroll-confirm"
        />
      )}
    </div>
  );
}

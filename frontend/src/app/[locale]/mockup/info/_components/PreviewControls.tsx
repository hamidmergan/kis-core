"use client";

import type { ReactNode } from "react";
import { useTranslations } from "next-intl";
import { Switch } from "../../../admin/_settings/fields";
import { useMockup } from "../../_lib/store";
import { MAX_TILES, type EventBlock } from "../../_lib/types";
import { withTileCount } from "../_lib/previewTiles";

const COUNTS = Array.from({ length: MAX_TILES }, (_, i) => i + 1);

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-4">
      <span className="text-sm text-foreground">{label}</span>
      {children}
    </div>
  );
}

/** Mockup-only controls, later the admin page owns these settings. */
export default function PreviewControls() {
  const t = useTranslations("mockup.info.preview");
  const [config, update] = useMockup("config");
  const block = config.eventBlock;
  const patchBlock = (next: Partial<EventBlock>) =>
    update((current) => ({ ...current, eventBlock: { ...current.eventBlock, ...next } }));
  const setCount = (count: number) =>
    update((current) => ({ ...current, eventBlock: withTileCount(current.eventBlock, count) }));
  return (
    <section className="rounded-xl border-2 border-dashed border-border p-5 flex flex-col gap-4" data-testid="preview-controls">
      <div>
        <h2 className="text-sm font-semibold text-foreground">{t("heading")}</h2>
        <p className="text-xs text-muted mt-1">{t("hint")}</p>
      </div>
      <Row label={t("blockOn")}>
        <Switch checked={block.enabled} onChange={(on) => patchBlock({ enabled: on })} label={t("blockOn")} />
      </Row>
      <Row label={t("tiles")}>
        <div role="group" aria-label={t("tiles")} className="flex gap-1.5">
          {COUNTS.map((count) => {
            const picked = block.tiles.length === count;
            return (
              <button
                key={count}
                type="button"
                aria-pressed={picked}
                onClick={() => setCount(count)}
                className={`w-9 h-9 text-sm rounded-full border-2 transition-colors ${
                  picked ? "border-kb bg-kb text-on-accent font-semibold" : "border-border text-foreground-soft hover:border-kb"
                }`}
              >
                {count}
              </button>
            );
          })}
        </div>
      </Row>
      <Row label={t("ignoreWindow")}>
        <Switch checked={block.ignoreWindow} onChange={(on) => patchBlock({ ignoreWindow: on })} label={t("ignoreWindow")} />
      </Row>
    </section>
  );
}

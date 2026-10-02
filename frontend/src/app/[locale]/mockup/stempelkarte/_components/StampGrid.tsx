"use client";

import { useTranslations } from "next-intl";
import { Check } from "@phosphor-icons/react";
import { MOCKUP_ICONS } from "../../_lib/icons";
import type { MockupCard, Station } from "../../_lib/types";
import { useText2 } from "../../_lib/useText2";

/** Name and icon per stand, no numbers, the freshly stamped tile lands with a short press. */
export default function StampGrid({
  stations,
  card,
  pulseId,
}: {
  stations: Station[];
  card: MockupCard;
  pulseId: string | null;
}) {
  const t = useTranslations("mockup.stamp");
  const text = useText2();
  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 gap-3" data-testid="stamp-grid">
      <style>{`
        @keyframes mockup-stamp-press {
          0% { transform: scale(1.18) rotate(-6deg); opacity: 0.35; }
          60% { transform: scale(0.97) rotate(1deg); opacity: 1; }
          100% { transform: scale(1) rotate(0deg); opacity: 1; }
        }
        .mockup-stamp-pulse { animation: mockup-stamp-press 450ms ease-out; }
        @media (prefers-reduced-motion: reduce) { .mockup-stamp-pulse { animation: none; } }
      `}</style>
      {stations.map((station) => {
        const done = station.id in card.stamped;
        const Icon = MOCKUP_ICONS[station.icon];
        return (
          <div
            key={`${station.id}:${card.stamped[station.id] ?? 0}`}
            data-testid="stamp-tile"
            data-stamped={done ? "true" : "false"}
            className={`flex flex-col items-center gap-2 rounded-2xl border-2 p-4 text-center ${
              done ? "border-kb bg-kb text-on-accent" : "border-dashed border-border bg-background text-foreground-soft"
            } ${pulseId === station.id ? "mockup-stamp-pulse" : ""}`}
          >
            <span
              className={`relative flex items-center justify-center w-12 h-12 rounded-full ${
                done ? "bg-background/15" : "bg-surface"
              }`}
            >
              <Icon size={26} weight={done ? "fill" : "regular"} aria-hidden="true" />
              {done && (
                <span className="absolute -right-1 -bottom-1 flex items-center justify-center w-5 h-5 rounded-full bg-background text-kb">
                  <Check size={12} weight="bold" aria-hidden="true" />
                </span>
              )}
            </span>
            <span className="text-sm font-semibold leading-snug break-words min-w-0 w-full">{text(station.name)}</span>
            <span className={`text-xs ${done ? "text-on-accent/80" : "text-muted"}`}>{done ? t("done") : t("open")}</span>
          </div>
        );
      })}
    </div>
  );
}

"use client";

import { useTranslations } from "next-intl";
import Band from "../info/_components/Band";
import { eventActive } from "../_lib/eventWindow";
import { useMockup } from "../_lib/store";
import { useText2 } from "../_lib/useText2";
import EventTile from "./EventTile";

const GRID: Record<number, string> = {
  1: "@min-[40rem]:grid-cols-1 @min-[64rem]:max-w-md",
  2: "@min-[40rem]:grid-cols-2 @min-[64rem]:max-w-4xl",
  3: "@min-[40rem]:grid-cols-3",
  4: "@min-[40rem]:grid-cols-2 @min-[64rem]:grid-cols-4",
};

/** Event section of the info page, shown while the admin has it on and today lies inside its period. */
export default function EventBlock({ bleed = false }: { bleed?: boolean }) {
  const t = useTranslations("mockup.event");
  const text = useText2();
  const [config] = useMockup("config");
  const block = config.eventBlock;
  if (!eventActive(block)) return bleed ? null : <p className="text-sm text-foreground-soft">{t("hidden")}</p>;
  const tiles = block.tiles.slice(0, 4);
  const content = (
    <div className="flex flex-col items-center gap-8" data-testid="event-block">
      <div className="max-w-3xl mx-auto text-center">
        <h2 className="text-3xl @min-[40rem]:text-4xl font-semibold tracking-[-0.02em] leading-tight text-on-accent!">
          {text(block.heading)}
        </h2>
        {block.text.de || block.text.en ? (
          <p className="text-lg @min-[40rem]:text-xl leading-relaxed text-on-accent/85 mt-3 text-balance">{text(block.text)}</p>
        ) : null}
      </div>
      {tiles.length > 0 && (
        <div className={`grid grid-cols-1 gap-4 @min-[64rem]:gap-6 w-full mx-auto ${GRID[tiles.length]}`}>
          {tiles.map((tile) => (
            <EventTile key={tile.id} tile={tile} />
          ))}
        </div>
      )}
    </div>
  );
  if (bleed) return <Band tone="accent">{content}</Band>;
  return <div className="@container rounded-2xl bg-kb text-on-accent p-6">{content}</div>;
}

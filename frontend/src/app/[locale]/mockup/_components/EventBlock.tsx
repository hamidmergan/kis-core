"use client";

import { useTranslations } from "next-intl";
import { eventActive } from "../_lib/eventWindow";
import { useMockup } from "../_lib/store";
import { useText2 } from "../_lib/useText2";
import EventTile from "./EventTile";

const GRID: Record<number, string> = {
  1: "sm:grid-cols-1",
  2: "sm:grid-cols-2",
  3: "sm:grid-cols-3",
  4: "sm:grid-cols-2 lg:grid-cols-4",
};

/** Top block of the info page, shown while the admin has it on and today lies inside its period. */
export default function EventBlock({ hintWhenHidden = false }: { hintWhenHidden?: boolean }) {
  const t = useTranslations("mockup.event");
  const text = useText2();
  const [config] = useMockup("config");
  const block = config.eventBlock;
  if (!eventActive(block)) {
    return hintWhenHidden ? <p className="text-sm text-foreground-soft">{t("hidden")}</p> : null;
  }
  const tiles = block.tiles.slice(0, 4);
  return (
    <section
      className="border-2 border-kb/15 bg-kb/5 rounded-2xl p-5 sm:p-6 flex flex-col gap-4"
      data-testid="event-block"
    >
      <div>
        <h2 className="text-2xl font-semibold tracking-[-0.01em] text-foreground">{text(block.heading)}</h2>
        {block.text.de || block.text.en ? (
          <p className="text-base text-foreground-soft mt-1">{text(block.text)}</p>
        ) : null}
      </div>
      {tiles.length > 0 && (
        <div className={`grid grid-cols-1 gap-4 ${GRID[tiles.length]}`}>
          {tiles.map((tile) => (
            <EventTile key={tile.id} tile={tile} />
          ))}
        </div>
      )}
    </section>
  );
}

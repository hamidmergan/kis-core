"use client";

import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { useRouter } from "@/i18n/navigation";
import { useMascotPref } from "@/hooks/useMascotPref";
import { ROUTES } from "../../_lib/routes";
import { useMockup } from "../../_lib/store";
import { isComplete, stamp, stampedIds, suggestNext, syncCompletion } from "../_lib/stampLogic";
import CodeEntry from "./CodeEntry";
import CompletionScreen from "./CompletionScreen";
import FrancisChatModal from "./FrancisChatModal";
import FrancisHint, { type HintMood } from "./FrancisHint";
import LoginOptional from "./LoginOptional";
import SimulationPanel from "./SimulationPanel";
import StampGrid from "./StampGrid";

export default function StampCard() {
  const t = useTranslations("mockup.stamp");
  const router = useRouter();
  const searchParams = useSearchParams();
  const { variant } = useMascotPref();
  const [config] = useMockup("config");
  const [card, updateCard] = useMockup("card");
  const stations = config.stations;
  const [mood, setMood] = useState<HintMood>({ kind: "welcome" });
  const [pulseId, setPulseId] = useState<string | null>(null);
  const [chatOpen, setChatOpen] = useState(false);
  const [ready, setReady] = useState(false);

  // The first effect pass still sees the server snapshot, the store catches up in the same flush.
  useEffect(() => setReady(true), []);

  const doStamp = useCallback(
    (id: string) => {
      const station = stations.find((s) => s.id === id);
      if (!station) return;
      updateCard((c) => stamp(c, stations, id, Date.now()));
      setMood({ kind: "stamped", station });
      setPulseId(id);
    },
    [stations, updateCard],
  );

  // A scanned QR code lands here with the stand in the query, unknown ids are dropped quietly.
  const scanned = searchParams.get("stand");
  useEffect(() => {
    if (!ready || !scanned) return;
    doStamp(scanned);
    router.replace(ROUTES.stamp, { scroll: false });
  }, [ready, scanned, doStamp, router]);

  useEffect(() => {
    if (!ready) return;
    const synced = syncCompletion(card, stations, Date.now());
    if (synced !== card) updateCard(() => synced);
  }, [ready, card, stations, updateCard]);

  const complete = isComplete(card, stations);
  const doneCount = stampedIds(card, stations).length;
  const lastId = mood.kind === "stamped" ? mood.station.id : null;

  return (
    <main className="max-w-3xl mx-auto px-4 py-6 sm:py-8 flex flex-col gap-6" data-testid="stamp-card">
      <div>
        <h1 className="text-2xl font-semibold tracking-[-0.01em] text-foreground">{t("title")}</h1>
        <p className="text-base text-foreground-soft mt-1">{t("intro")}</p>
      </div>
      {complete ? (
        <CompletionScreen variant={variant} completedAt={card.completedAt} />
      ) : (
        <>
          <p className="text-sm font-medium text-foreground-soft tabular-nums" data-testid="stamp-progress">
            {t("progress", { done: doneCount, total: stations.length })}
          </p>
          <StampGrid stations={stations} card={card} pulseId={pulseId} />
          <FrancisHint variant={variant} mood={mood} next={suggestNext(card, stations, lastId)} onAsk={() => setChatOpen(true)} />
          <CodeEntry onStamp={doStamp} onWrong={() => setMood({ kind: "wrong" })} />
        </>
      )}
      <LoginOptional linked={card.linkedToAccount} onToggle={() => updateCard({ linkedToAccount: !card.linkedToAccount })} />
      <SimulationPanel onScan={doStamp} />
      <FrancisChatModal open={chatOpen} onClose={() => setChatOpen(false)} variant={variant} />
    </main>
  );
}

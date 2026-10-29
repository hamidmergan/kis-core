"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { useRouter } from "@/i18n/navigation";
import { useMascotPref } from "@/hooks/useMascotPref";
import { ROUTES } from "@/lib/event/routes";
import { isComplete, stampedIds, suggestNext } from "@/lib/event/stampLogic";
import { usePublicEvent } from "@/lib/event/usePublicEvent";
import { useStampCard } from "@/lib/event/useStampCard";
import { useText2 } from "@/lib/event/useText2";
import CodeEntry from "./CodeEntry";
import CompletionScreen from "./CompletionScreen";
import RaffleEntry from "./RaffleEntry";
import StampGrid from "./StampGrid";
import StampNotice, { type HintMood } from "./StampNotice";
import VisitorCodeAccordion from "./VisitorCodeAccordion";

export default function StampCard() {
  const t = useTranslations("eventStamp");
  const router = useRouter();
  const searchParams = useSearchParams();
  const { variant } = useMascotPref();
  const text = useText2();
  const { data, failed } = usePublicEvent();
  const { card, ready, failed: cardFailed, stamp, submitCode, enterRaffle } = useStampCard();
  const stations = data?.stations ?? [];
  const [mood, setMood] = useState<HintMood>({ kind: "welcome" });
  const [pulseId, setPulseId] = useState<string | null>(null);

  const doStamp = useCallback(
    async (id: string) => {
      const station = stations.find((s) => s.id === id);
      if (!station || !(await stamp(id))) return;
      setMood({ kind: "stamped", station });
      setPulseId(id);
    },
    [stations, stamp],
  );

  // A scanned QR code lands here with the stand in the query, unknown ids are dropped quietly.
  const scanned = searchParams.get("stand");
  const handled = useRef(false);
  useEffect(() => {
    if (!ready || !data || !scanned || handled.current) return;
    handled.current = true;
    void doStamp(scanned);
    router.replace(ROUTES.stamp, { scroll: false });
  }, [ready, data, scanned, doStamp, router]);

  const loading = !ready || !data;
  const complete = isComplete(card, stations);
  const showComplete = !failed && !cardFailed && !loading && complete;
  const doneCount = stampedIds(card, stations).length;
  const lastId = mood.kind === "stamped" ? mood.station.id : null;

  return (
    <main className="max-w-3xl mx-auto px-4 py-6 sm:py-8 flex flex-col gap-6" data-testid="stamp-card">
      <div>
        <h1 className="text-2xl font-semibold tracking-[-0.01em] text-foreground">
          {data ? text(data.cardTexts.title) : t("title")}
        </h1>
        {!showComplete && data && <p className="text-base text-foreground-soft mt-1">{text(data.cardTexts.intro)}</p>}
      </div>
      {failed || cardFailed ? (
        <p className="text-sm text-error" role="alert">
          {t("loadFailed")}
        </p>
      ) : loading ? (
        <p className="text-sm text-foreground-soft">{t("loading")}</p>
      ) : showComplete ? (
        <>
          <CompletionScreen
            variant={variant}
            completedAt={card.completedAt}
            title={text(data.cardTexts.completeTitle)}
            reward={text(data.cardTexts.completeText)}
          />
          {data?.raffle && <RaffleEntry raffle={data.raffle} email={card.raffleEmail} enter={enterRaffle} />}
        </>
      ) : (
        <>
          <StampNotice mood={mood} next={suggestNext(card, stations, lastId)} />
          <p className="text-sm font-medium text-foreground-soft tabular-nums" data-testid="stamp-progress">
            {t("progress", { done: doneCount, total: stations.length })}
          </p>
          <StampGrid stations={stations} card={card} pulseId={pulseId} />
          <CodeEntry
            card={card}
            submitCode={submitCode}
            onStamped={(id) => void doStamp(id)}
            onWrong={() => setMood({ kind: "wrong" })}
          />
          <VisitorCodeAccordion code={card.code} />
        </>
      )}
    </main>
  );
}

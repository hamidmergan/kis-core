"use client";

/** Who got counted in one bar of the hour or day chart. */

import { useTranslations } from "next-intl";
import { Ladeanzeige } from "./_bausteine";
import { useStatistik } from "./_laden";

interface BucketNutzer { id: number; name: string }

type Bucket =
  | { art: "hour"; hour: number }
  | { art: "day"; day: string }
  | { art: "month"; month: string };

function pfad(bucket: Bucket): string {
  switch (bucket.art) {
    case "hour":
      return `/api/admin/stats/users/today/${bucket.hour}`;
    case "day":
      return `/api/admin/stats/users/by-day/${bucket.day}`;
    case "month":
      return `/api/admin/stats/users/by-month?month=${encodeURIComponent(bucket.month)}`;
  }
}

export function BucketAnsicht({ bucket }: { bucket: Bucket }) {
  const t = useTranslations("admin.statistik");
  const { daten, fehler } = useStatistik<{ users: BucketNutzer[] }>(pfad(bucket));

  if (fehler) return <p className="text-sm text-error">{t("loadError")}</p>;
  if (!daten) return <Ladeanzeige />;
  const nutzer = daten.users;
  if (nutzer.length === 0) return <p className="text-sm text-muted-soft">{t("users.bucketEmpty")}</p>;

  return (
    <ul className="divide-y divide-border-soft">
      {nutzer.map((n) => (
        <li key={n.id} className="py-2 text-sm text-foreground-soft">
          {n.name}
        </li>
      ))}
    </ul>
  );
}

export type { Bucket };

"use client";

/** Who got counted in one bar of the hour or day chart. */

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { Ladeanzeige } from "./_bausteine";

interface BucketNutzer { id: number; name: string }

type Bucket = { art: "hour"; hour: number } | { art: "day"; day: string };

function pfad(bucket: Bucket): string {
  return bucket.art === "hour"
    ? `/api/admin/stats/users/today/${bucket.hour}`
    : `/api/admin/stats/users/by-day/${bucket.day}`;
}

export function BucketAnsicht({ bucket }: { bucket: Bucket }) {
  const t = useTranslations("admin.statistik");
  const [nutzer, setNutzer] = useState<BucketNutzer[] | null>(null);
  const [fehler, setFehler] = useState(false);

  useEffect(() => {
    setNutzer(null);
    setFehler(false);
    fetch(pfad(bucket), { credentials: "include" })
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then((d) => setNutzer(d.users))
      .catch(() => setFehler(true));
  }, [bucket.art, bucket.art === "hour" ? bucket.hour : bucket.day]);

  if (fehler) return <p className="text-sm text-error">{t("loadError")}</p>;
  if (!nutzer) return <Ladeanzeige />;
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

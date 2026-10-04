"use client";

import { useCallback, useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { Prohibit } from "@phosphor-icons/react";
import { SettingCard } from "@/app/[locale]/admin/_settings/fields";
import { backendApi } from "@/lib/api";

interface PageRow {
  id: number;
  url: string;
  title: string | null;
  status: string;
  chunk_count: number;
}

interface PagesOut {
  items: PageRow[];
  total: number;
  excluded: { url: string }[];
}

const LIMIT = 50;
const INPUT = "rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground focus:outline-none focus:border-kb";
const BTN = "px-3 py-1.5 text-xs rounded-md border-2 border-border text-foreground-soft hover:border-kb transition-colors disabled:opacity-60 whitespace-nowrap";

export default function PagesList({ refreshKey }: { refreshKey: number }) {
  const t = useTranslations("admin.sections.campus.pages");
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("");
  const [offset, setOffset] = useState(0);
  const [data, setData] = useState<PagesOut | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    const params = new URLSearchParams({ q: query, status, limit: String(LIMIT), offset: String(offset) });
    setData(await backendApi.getJson<PagesOut>(`/admin/campus/pages?${params}`));
  }, [query, status, offset]);

  // A short pause after typing keeps the list from asking on every key.
  useEffect(() => {
    const id = setTimeout(() => load().catch(() => undefined), 250);
    return () => clearTimeout(id);
  }, [load, refreshKey]);

  const change = async (path: string, url: string) => {
    setBusy(true);
    try {
      await backendApi.postJson(path, { url });
      await load();
    } finally {
      setBusy(false);
    }
  };

  const total = data?.total ?? 0;
  return (
    <SettingCard title={t("title")} description={t("hint")}>
      <div className="mt-3 flex flex-col gap-3">
        <div className="flex gap-2 flex-wrap">
          <input value={query} onChange={(e) => { setQuery(e.target.value); setOffset(0); }} placeholder={t("search")} className={`${INPUT} flex-1 min-w-48`} />
          <select value={status} onChange={(e) => { setStatus(e.target.value); setOffset(0); }} className={INPUT}>
            <option value="">{t("all")}</option>
            {(["ready", "pending", "failed"] as const).map((s) => <option key={s} value={s}>{t(`status.${s}`)}</option>)}
          </select>
        </div>
        <p className="text-xs text-muted">{t("total", { n: total })}</p>
        {data && data.items.length === 0 ? (
          <p className="text-xs text-muted">{t("none")}</p>
        ) : (
          <ul className="flex flex-col divide-y divide-border-soft">
            {data?.items.map((p) => (
              <li key={p.id} className="flex items-center gap-3 py-2 text-sm">
                <div className="flex-1 min-w-0">
                  <div className="truncate">{p.title || p.url}</div>
                  <a href={p.url} target="_blank" rel="noopener noreferrer" className="block truncate text-2xs text-muted hover:underline">{p.url}</a>
                </div>
                <span className="text-xs text-muted whitespace-nowrap">
                  {p.status === "ready" ? t("chunks", { n: p.chunk_count }) : t(`status.${p.status}` as "status.ready")}
                </span>
                <button type="button" onClick={() => change("/admin/campus/pages/exclude", p.url)} disabled={busy} title={t("exclude")} className="w-7 h-7 flex items-center justify-center rounded-full btn-icon" style={{ backgroundColor: "var(--surface-dim)" }}>
                  <Prohibit size={13} weight="bold" />
                </button>
              </li>
            ))}
          </ul>
        )}
        {total > LIMIT && (
          <div className="flex items-center gap-2">
            <button type="button" className={BTN} disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - LIMIT))}>{t("prev")}</button>
            <button type="button" className={BTN} disabled={offset + LIMIT >= total} onClick={() => setOffset(offset + LIMIT)}>{t("next")}</button>
          </div>
        )}
        {data && data.excluded.length > 0 && (
          <div className="mt-2">
            <h4 className="text-xs font-medium text-muted mb-1">{t("excluded")}</h4>
            <ul className="flex flex-col divide-y divide-border-soft">
              {data.excluded.map((e) => (
                <li key={e.url} className="flex items-center gap-3 py-2 text-sm">
                  <span className="flex-1 min-w-0 truncate">{e.url}</span>
                  <button type="button" className={BTN} disabled={busy} onClick={() => change("/admin/campus/pages/include", e.url)}>{t("include")}</button>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </SettingCard>
  );
}

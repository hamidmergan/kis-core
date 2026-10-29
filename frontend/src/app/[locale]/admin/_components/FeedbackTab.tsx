"use client";

/** Anonymous feedback: compact list, one click leads to the details. */

import { useCallback, useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { Paperclip, Trash } from "@phosphor-icons/react";
import IconButton from "@/components/ui/IconButton";
import Select from "@/components/ui/Select";
import Spinner from "@/components/ui/Spinner";
import Tabs from "@/components/ui/Tabs";
import StatusMark from "@/components/ui/StatusMark";
import type { StatusTone } from "@/lib/jobStatusDisplay";
import { announceFeedbackChange } from "@/hooks/useOpenFeedback";

type Category = "bug" | "idea" | "other";

type FeedbackStatus = "open" | "parked" | "done";

const STATUSES: readonly FeedbackStatus[] = ["open", "parked", "done"];

type Filter = FeedbackStatus | "all";

const FILTERS: readonly Filter[] = ["open", "parked", "done", "all"];

// The stripe on the left tells the status at a glance, without opening the select.
const STRIPE: Record<FeedbackStatus, string> = {
  open: "var(--error)",
  parked: "var(--warn)",
  done: "var(--success)",
};

type Attachment = {
  id: number;
  filename: string;
};

type Entry = {
  id: number;
  category: Category;
  message: string;
  contact: string | null;
  username: string | null;
  page_path: string | null;
  status: FeedbackStatus;
  created_at: string;
  attachments: Attachment[];
};

const TON: Record<Category, StatusTone> = {
  bug: "error",
  idea: "success",
  other: "muted",
};

function datum(wert: string): string {
  return new Date(wert).toLocaleString("de-DE", { dateStyle: "short", timeStyle: "short" });
}

export default function FeedbackTab({ onOpen }: { onOpen: (id: number) => void }) {
  const t = useTranslations("admin.feedback");
  const [entries, setEntries] = useState<Entry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [filter, setFilter] = useState<Filter>("open");

  const laden = useCallback(() => {
    fetch("/api/admin/feedback", { credentials: "include" })
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error("load"))))
      .then((d) => setEntries(d.feedback ?? []))
      .catch(() => setError(t("loadError")))
      .finally(() => setLoading(false));
  }, [t]);

  useEffect(laden, [laden]);

  async function setStatus(entry: Entry, status: FeedbackStatus) {
    setEntries((prev) => prev.map((e) => (e.id === entry.id ? { ...e, status } : e)));
    const r = await fetch(`/api/admin/feedback/${entry.id}`, {
      method: "PATCH",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status }),
    });
    if (!r.ok) {
      setEntries((prev) => prev.map((e) => (e.id === entry.id ? { ...e, status: entry.status } : e)));
      setError(t("saveError"));
      return;
    }
    announceFeedbackChange();
  }

  async function loeschen(entry: Entry) {
    const r = await fetch(`/api/admin/feedback/${entry.id}`, {
      method: "DELETE",
      credentials: "include",
    });
    if (!r.ok) {
      setError(t("deleteError"));
      return;
    }
    setEntries((prev) => prev.filter((e) => e.id !== entry.id));
    announceFeedbackChange();
  }

  // The open view holds everything not done, untouched entries first, parked ones below.
  const inFilter = (e: Entry, f: Filter) =>
    f === "all" || e.status === f || (f === "open" && e.status === "parked");
  const count = (f: Filter) => entries.filter((e) => inFilter(e, f)).length;
  const shown = entries
    .filter((e) => inFilter(e, filter))
    .sort((x, y) => (filter === "open" ? Number(x.status === "parked") - Number(y.status === "parked") : 0));
  const statusOptions = STATUSES.map((s) => ({ value: s, label: t(`status.${s}`) }));

  return (
    <div className="space-y-3">
      <Tabs<Filter>
        variant="pill"
        active={filter}
        onChange={setFilter}
        items={FILTERS.map((f) => ({
          key: f,
          label: f === "all" ? t("filterAll") : t(`status.${f}`),
          badge: <span className="text-xs opacity-75">{count(f)}</span>,
        }))}
      />

      {error && <p className="text-xs text-error">{error}</p>}

      {loading ? (
        <Spinner className="flex justify-center py-12" />
      ) : shown.length === 0 ? (
        <p className="text-sm text-muted-soft text-center py-8">
          {entries.length === 0 || filter === "all" ? t("empty") : t(`emptyStatus.${filter}`)}
        </p>
      ) : (
        <ul className="divide-y divide-border-soft border border-border-soft rounded-xl overflow-hidden">
          {shown.map((e) => (
            <li
              key={e.id}
              onClick={() => onOpen(e.id)}
              className="px-5 py-4 bg-background flex items-stretch justify-between gap-4 cursor-pointer hover:bg-surface transition-colors border-l-4"
              style={{ borderLeftColor: STRIPE[e.status] }}
            >
              <div className={`min-w-0 flex-1${e.status === "done" ? " opacity-55" : ""}`}>
                <div className="flex items-center gap-2 mb-1">
                  <StatusMark tone={TON[e.category]} className="text-xs">
                    {t(`category${e.category[0].toUpperCase()}${e.category.slice(1)}` as
                      "categoryBug" | "categoryIdea" | "categoryOther")}
                  </StatusMark>
                  <span className="text-xs text-muted-soft whitespace-nowrap">{datum(e.created_at)}</span>
                  {e.attachments.length > 0 && (
                    <span className="inline-flex items-center gap-1 text-xs text-muted-soft">
                      <Paperclip size={11} />
                      {e.attachments.length}
                    </span>
                  )}
                </div>
                <p className="text-sm text-foreground truncate">{e.message}</p>
                <p className="text-xs text-muted-soft mt-0.5">{e.username || t("anonymous")}</p>
              </div>
              <div
                className="flex flex-col items-end justify-between shrink-0"
                onClick={(ev) => ev.stopPropagation()}
              >
                <IconButton size="sm" onClick={() => void loeschen(e)} aria-label={t("delete")}>
                  <Trash size={13} />
                </IconButton>
                <Select
                  size="sm"
                  value={e.status}
                  onChange={(s) => void setStatus(e, s)}
                  options={statusOptions}
                  ariaLabel={t("statusAria")}
                />
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

"use client";

/** Anonyme Rückmeldungen: kompakte Liste, ein Klick führt zu den Details. */

import { useCallback, useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { Paperclip, Trash } from "@phosphor-icons/react";
import Checkbox from "@/components/ui/Checkbox";
import IconButton from "@/components/ui/IconButton";
import Spinner from "@/components/ui/Spinner";
import StatusMark from "@/components/ui/StatusMark";
import type { StatusTone } from "@/lib/jobStatusDisplay";

type Category = "bug" | "idea" | "other";

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
  done: boolean;
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

  const laden = useCallback(() => {
    fetch("/api/admin/feedback", { credentials: "include" })
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error("load"))))
      .then((d) => setEntries(d.feedback ?? []))
      .catch(() => setError(t("loadError")))
      .finally(() => setLoading(false));
  }, [t]);

  useEffect(laden, [laden]);

  async function toggleDone(entry: Entry) {
    const naechsterStand = !entry.done;
    setEntries((prev) => prev.map((e) => (e.id === entry.id ? { ...e, done: naechsterStand } : e)));
    const r = await fetch(`/api/admin/feedback/${entry.id}`, {
      method: "PATCH",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ done: naechsterStand }),
    });
    if (!r.ok) {
      setEntries((prev) => prev.map((e) => (e.id === entry.id ? { ...e, done: entry.done } : e)));
      setError(t("saveError"));
    }
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
  }

  const offen = entries.filter((e) => !e.done).length;

  return (
    <div className="space-y-3">
      <span className="text-xs text-muted-soft">
        {t("summary", { n: entries.length, offen })}
      </span>

      {error && <p className="text-xs text-error">{error}</p>}

      {loading ? (
        <Spinner className="flex justify-center py-12" />
      ) : entries.length === 0 ? (
        <p className="text-sm text-muted-soft text-center py-8">{t("empty")}</p>
      ) : (
        <ul className="divide-y divide-border-soft border border-border-soft rounded-xl overflow-hidden">
          {entries.map((e) => (
            <li
              key={e.id}
              onClick={() => onOpen(e.id)}
              className="px-5 py-4 bg-background flex items-center justify-between gap-4 cursor-pointer hover:bg-surface transition-colors"
            >
              <div className="min-w-0 flex-1">
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
              <div className="flex items-center gap-2 shrink-0" onClick={(ev) => ev.stopPropagation()}>
                <Checkbox checked={e.done} onChange={() => void toggleDone(e)} label={t("doneAria")} />
                <IconButton size="sm" onClick={() => void loeschen(e)} aria-label={t("delete")}>
                  <Trash size={13} />
                </IconButton>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

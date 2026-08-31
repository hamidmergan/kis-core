"use client";

/** Anonyme Rückmeldungen: Liste, erledigt markieren, löschen. */

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

export default function FeedbackTab() {
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
        <div className="overflow-x-auto">
          <table className="w-full text-sm border border-border-soft rounded-xl overflow-hidden">
            <thead className="bg-surface text-xs text-muted uppercase">
              <tr>
                <th className="px-4 py-3 text-left">{t("colDate")}</th>
                <th className="px-4 py-3 text-left">{t("colCategory")}</th>
                <th className="px-4 py-3 text-left">{t("colMessage")}</th>
                <th className="px-4 py-3 text-left">{t("colFrom")}</th>
                <th className="px-4 py-3 text-left">{t("colContact")}</th>
                <th className="px-4 py-3 text-left">{t("colDone")}</th>
                <th className="px-4 py-3 text-left">{t("colActions")}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border-soft bg-background">
              {entries.map((e) => (
                <tr key={e.id}>
                  <td className="px-4 py-3 text-foreground-soft whitespace-nowrap">{datum(e.created_at)}</td>
                  <td className="px-4 py-3">
                    <StatusMark tone={TON[e.category]} className="text-xs">
                      {t(`category${e.category[0].toUpperCase()}${e.category.slice(1)}` as
                        "categoryBug" | "categoryIdea" | "categoryOther")}
                    </StatusMark>
                  </td>
                  <td className="px-4 py-3 max-w-md">
                    <p className="whitespace-pre-line break-words">{e.message}</p>
                    {e.page_path && (
                      <p className="text-2xs text-muted-soft mt-1">{e.page_path}</p>
                    )}
                    {e.attachments.length > 0 && (
                      <ul className="mt-1.5 space-y-1">
                        {e.attachments.map((a) => (
                          <li key={a.id}>
                            <a
                              href={`/api/admin/feedback/attachments/${a.id}`}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="inline-flex items-center gap-1 text-2xs text-kb hover:underline"
                            >
                              <Paperclip size={11} />
                              {a.filename}
                            </a>
                          </li>
                        ))}
                      </ul>
                    )}
                  </td>
                  <td className="px-4 py-3 text-foreground-soft">{e.username || t("anonymous")}</td>
                  <td className="px-4 py-3 text-foreground-soft">{e.contact || "—"}</td>
                  <td className="px-4 py-3">
                    <Checkbox checked={e.done} onChange={() => void toggleDone(e)} label={t("doneAria")} />
                  </td>
                  <td className="px-4 py-3">
                    <IconButton size="sm" onClick={() => void loeschen(e)} aria-label={t("delete")}>
                      <Trash size={13} />
                    </IconButton>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

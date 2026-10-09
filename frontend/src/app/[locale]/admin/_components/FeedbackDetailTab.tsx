"use client";

/** Eine Rückmeldung, vollständig dargestellt. */

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { Paperclip, Trash } from "@phosphor-icons/react";
import IconButton from "@/components/ui/IconButton";
import Select from "@/components/ui/Select";
import Spinner from "@/components/ui/Spinner";
import StatusMark from "@/components/ui/StatusMark";
import type { StatusTone } from "@/lib/jobStatusDisplay";
import { announceFeedbackChange } from "@/hooks/useOpenFeedback";

type Category = "bug" | "idea" | "other";

type FeedbackStatus = "open" | "parked" | "done";

const STATUSES: readonly FeedbackStatus[] = ["open", "parked", "done"];

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

export default function FeedbackDetailTab({ id, onBack }: { id: number; onBack: () => void }) {
  const t = useTranslations("admin.feedback");
  const [entry, setEntry] = useState<Entry | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    fetch("/api/admin/feedback", { credentials: "include" })
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error("load"))))
      .then((d) => setEntry((d.feedback ?? []).find((e: Entry) => e.id === id) ?? null))
      .catch(() => setError(t("loadError")))
      .finally(() => setLoading(false));
  }, [id, t]);

  async function setStatus(status: FeedbackStatus) {
    if (!entry) return;
    const vorher = entry.status;
    setEntry({ ...entry, status });
    const r = await fetch(`/api/admin/feedback/${entry.id}`, {
      method: "PATCH",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status }),
    });
    if (!r.ok) {
      setEntry((prev) => (prev ? { ...prev, status: vorher } : prev));
      setError(t("saveError"));
      return;
    }
    announceFeedbackChange();
  }

  async function loeschen() {
    if (!entry) return;
    const r = await fetch(`/api/admin/feedback/${entry.id}`, {
      method: "DELETE",
      credentials: "include",
    });
    if (!r.ok) {
      setError(t("deleteError"));
      return;
    }
    announceFeedbackChange();
    onBack();
  }

  return (
    <div className="space-y-4">
      <button onClick={onBack} className="text-sm text-kb hover:underline">
        {t("back")}
      </button>

      {error && <p className="text-xs text-error">{error}</p>}

      {loading ? (
        <Spinner className="flex justify-center py-12" />
      ) : !entry ? (
        <p className="text-sm text-muted-soft text-center py-8">{t("notFound")}</p>
      ) : (
        <div className="border border-border-soft rounded-xl bg-background p-6 space-y-4">
          <div className="flex items-center justify-between gap-4">
            <div className="flex items-center gap-2">
              <StatusMark tone={TON[entry.category]} className="text-xs">
                {t(`category${entry.category[0].toUpperCase()}${entry.category.slice(1)}` as
                  "categoryBug" | "categoryIdea" | "categoryOther")}
              </StatusMark>
              <span className="text-xs text-muted-soft">{datum(entry.created_at)}</span>
            </div>
            <IconButton size="sm" onClick={() => void loeschen()} aria-label={t("delete")}>
              <Trash size={13} />
            </IconButton>
          </div>

          <p className="text-sm text-foreground whitespace-pre-line break-words">{entry.message}</p>

          {entry.page_path && <p className="text-xs text-muted-soft">{entry.page_path}</p>}

          {entry.attachments.length > 0 && (
            <ul className="space-y-1.5">
              {entry.attachments.map((a) => (
                <li key={a.id}>
                  <a
                    href={`/api/admin/feedback/attachments/${a.id}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 text-xs text-kb hover:underline"
                  >
                    <Paperclip size={12} />
                    {a.filename}
                  </a>
                </li>
              ))}
            </ul>
          )}

          <div className="flex items-center justify-between gap-4 pt-3 border-t border-border-soft">
            <span className="text-xs text-muted-soft">
              {entry.username || t("anonymous")}
              {entry.contact ? ` · ${entry.contact}` : ""}
            </span>
            <Select
              size="sm"
              value={entry.status}
              onChange={(s) => void setStatus(s)}
              options={STATUSES.map((s) => ({ value: s, label: t(`status.${s}`) }))}
              ariaLabel={t("statusAria")}
            />
          </div>
        </div>
      )}
    </div>
  );
}

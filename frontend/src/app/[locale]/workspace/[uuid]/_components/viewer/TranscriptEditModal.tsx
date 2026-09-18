"use client";

import { useEffect, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { WarningCircle } from "@phosphor-icons/react";
import Modal from "@/components/ui/Modal";
import Spinner from "@/components/ui/Spinner";
import { genericErrorMessage, parseDetail } from "@/lib/api";
import { langLabel } from "../../_types";

/** One line of one track, the index is its place in the whole transcript. */
export interface EditLine {
  index: number;
  text: string;
}

export interface EditTrack {
  lang: string;
  lines: EditLine[];
}

const MAX_LINE_LENGTH = 1000;

/** Corrects the lines of one paragraph, for everyone who may manage the workspace. */
export function TranscriptEditModal({
  open,
  onClose,
  tracks,
  timeLabel,
  workspaceUuid,
  sourceUuid,
  onSaved,
}: {
  open: boolean;
  onClose: () => void;
  /** The visible tracks of the paragraph, the original first. */
  tracks: EditTrack[];
  timeLabel: string;
  workspaceUuid: string;
  sourceUuid: string;
  onSaved: (lang: string, lines: EditLine[]) => void;
}) {
  const t = useTranslations("workspace.detail.viewer");
  const locale = useLocale();
  const [draft, setDraft] = useState<Record<string, string[]>>({});
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Every opening starts from the stored text, a cancelled edit leaves nothing behind.
  useEffect(() => {
    if (!open) return;
    const start: Record<string, string[]> = {};
    for (const track of tracks) start[track.lang] = track.lines.map((l) => l.text);
    setDraft(start);
    setError(null);
  }, [open, tracks]);

  const setLine = (lang: string, i: number, value: string) => {
    setDraft((cur) => {
      const lines = [...(cur[lang] ?? [])];
      lines[i] = value.slice(0, MAX_LINE_LENGTH);
      return { ...cur, [lang]: lines };
    });
  };

  // An emptied line would drop out of the file and pull the translation out of step.
  const hasEmpty = tracks.some((track) =>
    (draft[track.lang] ?? []).some((line) => !line.trim()),
  );
  const changed = tracks.filter((track) =>
    track.lines.some((line, i) => (draft[track.lang]?.[i] ?? line.text).trim() !== line.text),
  );

  const onSave = async () => {
    if (saving || hasEmpty || changed.length === 0) return;
    setSaving(true);
    setError(null);
    try {
      for (const track of changed) {
        const lines = track.lines.map((line, i) => ({
          index: line.index,
          text: (draft[track.lang]?.[i] ?? line.text).trim(),
        }));
        const res = await fetch(
          `/api/ai-assistant/workspaces/${workspaceUuid}/sources/${sourceUuid}/transcript`,
          {
            method: "PATCH",
            credentials: "include",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ lang: track.lang, cues: lines }),
          },
        );
        if (!res.ok) {
          const detail = (await res.json().catch(() => null))?.detail;
          throw new Error(parseDetail(detail, genericErrorMessage()));
        }
        onSaved(track.lang, lines);
      }
      onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : genericErrorMessage());
    } finally {
      setSaving(false);
    }
  };

  const fuss = (
    <>
      <button
        type="button"
        onClick={onClose}
        className="btn-cancel px-4 py-2 text-sm btn-secondary rounded-lg"
      >
        {t("transcriptEditCancel")}
      </button>
      <button
        type="button"
        onClick={onSave}
        disabled={saving || hasEmpty || changed.length === 0}
        className="px-4 py-2 text-sm btn-primary rounded-lg disabled:opacity-50 flex items-center gap-2"
      >
        {saving && <Spinner size="xs" color="current" />}
        {t("transcriptEditSave")}
      </button>
    </>
  );

  return (
    <Modal open={open} onClose={onClose} title={t("transcriptEditTitle")} size="lg" footer={fuss}>
      <div className="flex flex-col gap-4">
        <div
          className="flex items-start gap-2 rounded-lg px-3 py-2"
          style={{ backgroundColor: "var(--cite-bg)" }}
        >
          <span className="flex-shrink-0 mt-0.5" style={{ color: "var(--kb-dark)" }}>
            <WarningCircle size={16} weight="fill" />
          </span>
          <p className="text-xs leading-snug" style={{ color: "var(--foreground)" }}>
            {t("transcriptEditWarning")}
          </p>
        </div>
        <p className="text-xs font-mono" style={{ color: "var(--muted)" }}>
          {timeLabel}
        </p>

        {tracks.map((track) => (
          <div key={track.lang} className="flex flex-col gap-2">
            {tracks.length > 1 && (
              <span className="text-xs font-semibold uppercase tracking-wide" style={{ color: "var(--muted)" }}>
                {langLabel(track.lang, locale)}
              </span>
            )}
            {track.lines.map((line, i) => (
              <textarea
                key={line.index}
                value={draft[track.lang]?.[i] ?? line.text}
                onChange={(e) => setLine(track.lang, i, e.target.value)}
                rows={8}
                aria-label={t("transcriptEditLineLabel", { nr: i + 1 })}
                className="w-full rounded-lg border px-3 py-2 text-sm focus:outline-none focus:ring-2 resize-y"
                style={{
                  backgroundColor: "var(--background)",
                  borderColor: "var(--border)",
                  color: "var(--foreground)",
                }}
              />
            ))}
          </div>
        ))}

        {hasEmpty && (
          <p className="text-xs" style={{ color: "var(--error)" }}>{t("transcriptEditEmptyLine")}</p>
        )}
        {error && (
          <p className="text-xs" style={{ color: "var(--error)" }}>{error}</p>
        )}
      </div>
    </Modal>
  );
}

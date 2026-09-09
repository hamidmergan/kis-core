"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { UploadSimple } from "@phosphor-icons/react";
import Modal from "@/components/ui/Modal";
import Spinner from "@/components/ui/Spinner";
import CollapsibleCard from "@/components/ui/CollapsibleCard";
import HelpTooltip from "@/components/ui/HelpTooltip";

const fieldStyle = () => ({
  backgroundColor: "var(--background)",
  color: "var(--foreground)",
});

const fieldBorderClass = (error: boolean) =>
  error ? "border-error-border" : "border-border focus:border-kb";

/** One dialog for three ways in: a file, a web page by link, or a YouTube video with its transcript. */
export function AddMaterialModal({
  open,
  onClose,
  onPickFile,
  onAddLink,
  onAddYoutube,
}: {
  open: boolean;
  onClose: () => void;
  onPickFile: () => void;
  onAddLink: (url: string) => Promise<void>;
  onAddYoutube?: (url: string, transcript: string) => Promise<void>;
}) {
  const t = useTranslations("workspace.detail.sources");
  const [url, setUrl] = useState("");
  const [ytUrl, setYtUrl] = useState("");
  const [ytTranscript, setYtTranscript] = useState("");
  // Which section is running, the other one waits.
  const [busy, setBusy] = useState<"link" | "youtube" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [ytError, setYtError] = useState<string | null>(null);

  const reset = () => {
    setUrl("");
    setYtUrl("");
    setYtTranscript("");
    setError(null);
    setYtError(null);
  };

  const close = () => {
    if (busy) return;
    reset();
    onClose();
  };

  const submitLink = async () => {
    const value = url.trim();
    if (!value || busy) return;
    setBusy("link");
    setError(null);
    try {
      await onAddLink(value);
      reset();
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("linkFailed"));
    } finally {
      setBusy(null);
    }
  };

  const submitYoutube = async () => {
    const link = ytUrl.trim();
    const transcript = ytTranscript.trim();
    if (!link || !transcript || busy || !onAddYoutube) return;
    setBusy("youtube");
    setYtError(null);
    try {
      await onAddYoutube(link, transcript);
      reset();
      onClose();
    } catch (err) {
      setYtError(err instanceof Error ? err.message : t("youtubeFailed"));
    } finally {
      setBusy(null);
    }
  };

  return (
    <Modal
      open={open}
      onClose={close}
      title={t("addModalTitle")}
      size="md"
      closeOnBackdropClick={!busy}
      closeOnEscape={!busy}
    >
      <button
        type="button"
        onClick={() => { onPickFile(); close(); }}
        disabled={busy !== null}
        data-testid="add-material-file"
        className="add-source-btn w-full flex flex-col items-center gap-1 px-3 py-5 rounded-lg border-2 border-dashed transition-colors text-[var(--kb)] border-[rgba(var(--kb-rgb),0.35)] hover:border-[var(--kb)] disabled:opacity-40"
      >
        <UploadSimple size={20} weight="bold" />
        <span className="text-sm font-medium">{t("pickFile")}</span>
        <span className="text-xs" style={{ color: "var(--muted)" }}>{t("pickFileHint")}</span>
      </button>

      <div className="mt-4">
        <div className="text-3xs font-semibold uppercase tracking-wide mb-1.5" style={{ color: "var(--muted)" }}>
          {t("linkHeading")}
        </div>
        <form
          onSubmit={(e) => { e.preventDefault(); void submitLink(); }}
          className="flex items-center gap-2"
        >
          <input
            value={url}
            disabled={busy !== null}
            placeholder={t("linkPlaceholder")}
            data-testid="add-material-link"
            aria-label={t("linkHeading")}
            aria-describedby={error ? "add-material-link-error" : undefined}
            onChange={(e) => { setUrl(e.target.value); setError(null); }}
            className={`flex-1 min-w-0 rounded-lg border-2 px-3 py-2 text-sm focus:outline-none transition-colors ${fieldBorderClass(!!error)}`}
            style={fieldStyle()}
          />
          <button
            type="submit"
            disabled={busy !== null || !url.trim()}
            className="btn-primary px-4 py-2 rounded-lg text-sm font-medium disabled:opacity-50 whitespace-nowrap"
          >
            {busy === "link" ? <Spinner size="sm" color="current" /> : t("linkSubmit")}
          </button>
        </form>
        {error && (
          <p id="add-material-link-error" className="text-sm mt-2" style={{ color: "var(--error)" }}>{error}</p>
        )}
      </div>

      {onAddYoutube && (
        <div className="mt-4">
          <div className="text-3xs font-semibold uppercase tracking-wide mb-1.5 flex items-center gap-1.5" style={{ color: "var(--muted)" }}>
            <span>{t("youtubeHeading")}</span>
            {/* Says why the transcript is typed in by hand instead of fetched. */}
            <HelpTooltip text={t("youtubeWhyHelp")} />
          </div>
          <form
            onSubmit={(e) => { e.preventDefault(); void submitYoutube(); }}
            className="flex flex-col gap-2"
          >
            <input
              value={ytUrl}
              disabled={busy !== null}
              placeholder={t("youtubeLinkPlaceholder")}
              data-testid="add-material-youtube-link"
              aria-label={t("youtubeHeading")}
              aria-describedby={ytError ? "add-material-youtube-error" : undefined}
              onChange={(e) => { setYtUrl(e.target.value); setYtError(null); }}
              className={`w-full rounded-lg border-2 px-3 py-2 text-sm focus:outline-none transition-colors ${fieldBorderClass(!!ytError)}`}
              style={fieldStyle()}
            />
            <textarea
              value={ytTranscript}
              disabled={busy !== null}
              rows={4}
              placeholder={t("youtubeTranscriptPlaceholder")}
              data-testid="add-material-youtube-transcript"
              aria-label={t("youtubeTranscriptLabel")}
              aria-describedby={ytError ? "add-material-youtube-error" : undefined}
              onChange={(e) => { setYtTranscript(e.target.value); setYtError(null); }}
              className={`w-full rounded-lg border-2 px-3 py-2 text-sm focus:outline-none resize-y transition-colors ${fieldBorderClass(!!ytError)}`}
              style={fieldStyle()}
            />
            <CollapsibleCard title={t("youtubeHowTitle")}>
              <ol className="list-decimal pl-5 text-sm space-y-1" style={{ color: "var(--foreground-soft)" }}>
                <li>{t("youtubeHow1")}</li>
                <li>{t("youtubeHow2")}</li>
                <li>{t("youtubeHow3")}</li>
                <li>{t("youtubeHow4")}</li>
                <li>{t("youtubeHow5")}</li>
              </ol>
              <p className="text-sm mt-2" style={{ color: "var(--muted)" }}>{t("youtubeHowNoButton")}</p>
            </CollapsibleCard>
            <div className="flex justify-end">
              <button
                type="submit"
                disabled={busy !== null || !ytUrl.trim() || !ytTranscript.trim()}
                data-testid="add-material-youtube-submit"
                className="btn-primary px-4 py-2 rounded-lg text-sm font-medium disabled:opacity-50 whitespace-nowrap"
              >
                {busy === "youtube" ? <Spinner size="sm" color="current" /> : t("youtubeSubmit")}
              </button>
            </div>
          </form>
          {ytError && (
            <p id="add-material-youtube-error" className="text-sm mt-2" style={{ color: "var(--error)" }}>{ytError}</p>
          )}
        </div>
      )}
    </Modal>
  );
}

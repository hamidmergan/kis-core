"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { UploadSimple } from "@phosphor-icons/react";
import Modal from "@/components/ui/Modal";
import Spinner from "@/components/ui/Spinner";
import CollapsibleCard from "@/components/ui/CollapsibleCard";
import HelpTooltip from "@/components/ui/HelpTooltip";
import Select from "@/components/ui/Select";
import { TextSourceArea } from "./TextSourceArea";

const fieldStyle = () => ({
  backgroundColor: "var(--background)",
  color: "var(--foreground)",
});

const fieldBorderClass = (error: boolean) =>
  error ? "border-error-border" : "border-border focus:border-kb";

/** One dialog for the ways in: a file, a web page by link, a page from Pages, a YouTube video with its transcript, or pasted text. */
export function AddMaterialModal({
  open,
  onClose,
  onPickFile,
  onAddLink,
  onAddYoutube,
  onAddPage,
  onAddText,
  textMaxChars,
}: {
  open: boolean;
  onClose: () => void;
  onPickFile: () => void;
  onAddLink: (url: string) => Promise<void>;
  onAddYoutube?: (url: string, transcript: string) => Promise<void>;
  onAddPage?: (jobUuid: string) => Promise<void>;
  onAddText?: (title: string, text: string) => Promise<void>;
  textMaxChars?: number;
}) {
  const t = useTranslations("workspace.detail.sources");
  const [url, setUrl] = useState("");
  const [ytUrl, setYtUrl] = useState("");
  const [ytTranscript, setYtTranscript] = useState("");
  // Which section is running, the other one waits.
  const [busy, setBusy] = useState<"link" | "youtube" | "page" | "text" | null>(null);
  const [textTitle, setTextTitle] = useState("");
  const [textBody, setTextBody] = useState("");
  const [textError, setTextError] = useState<string | null>(null);
  // The person's finished pages, null while loading or when Pages is not theirs to use.
  const [pages, setPages] = useState<{ job_uuid: string; title: string }[] | null>(null);
  const [pageId, setPageId] = useState("");
  const [pageError, setPageError] = useState<string | null>(null);

  useEffect(() => {
    if (!open || !onAddPage) return;
    let cancelled = false;
    fetch("/api/pages", { credentials: "include" })
      .then((r) => (r.ok ? r.json() : null))
      .then((d: { pages?: { job_uuid: string; title: string; status: string }[] } | null) => {
        if (cancelled || !d?.pages) return;
        setPages(d.pages.filter((p) => p.status === "success").map((p) => ({ job_uuid: p.job_uuid, title: p.title })));
      })
      .catch(() => { /* Without Pages the section stays away. */ });
    return () => { cancelled = true; };
  }, [open, onAddPage]);
  const [error, setError] = useState<string | null>(null);
  const [ytError, setYtError] = useState<string | null>(null);

  const reset = () => {
    setUrl("");
    setYtUrl("");
    setYtTranscript("");
    setError(null);
    setYtError(null);
    setPageId("");
    setPageError(null);
    setTextTitle("");
    setTextBody("");
    setTextError(null);
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

  const submitPage = async () => {
    if (!pageId || busy || !onAddPage) return;
    setBusy("page");
    setPageError(null);
    try {
      await onAddPage(pageId);
      reset();
      onClose();
    } catch (err) {
      setPageError(err instanceof Error ? err.message : t("pageFailed"));
    } finally {
      setBusy(null);
    }
  };

  const textOver = !!textMaxChars && textBody.trim().length > textMaxChars;

  const submitText = async () => {
    const title = textTitle.trim();
    const body = textBody.trim();
    if (!title || !body || textOver || busy || !onAddText) return;
    setBusy("text");
    setTextError(null);
    try {
      await onAddText(title, body);
      reset();
      onClose();
    } catch (err) {
      setTextError(err instanceof Error ? err.message : t("textFailed"));
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

      {onAddPage && pages && (
        <div className="mt-4" data-testid="add-material-page">
          <div className="text-3xs font-semibold uppercase tracking-wide mb-1.5" style={{ color: "var(--muted)" }}>
            {t("pageHeading")}
          </div>
          {pages.length === 0 ? (
            <p className="text-sm" style={{ color: "var(--muted)" }}>{t("pageNone")}</p>
          ) : (
            <div className="flex items-center gap-2">
              <div className="flex-1 min-w-0">
                <Select
                  id="add-material-page-select"
                  ariaLabel={t("pageHeading")}
                  value={pageId}
                  onChange={(v) => { setPageId(v); setPageError(null); }}
                  disabled={busy !== null}
                  placeholder={t("pagePlaceholder")}
                  options={pages.map((p) => ({ value: p.job_uuid, label: p.title }))}
                />
              </div>
              <button
                type="button"
                onClick={() => void submitPage()}
                disabled={busy !== null || !pageId}
                data-testid="add-material-page-submit"
                className="btn-primary px-4 py-2 rounded-lg text-sm font-medium disabled:opacity-50 whitespace-nowrap"
              >
                {busy === "page" ? <Spinner size="sm" color="current" /> : t("pageSubmit")}
              </button>
            </div>
          )}
          {pageError && <p className="text-sm mt-2" style={{ color: "var(--error)" }}>{pageError}</p>}
        </div>
      )}

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

      {onAddText && textMaxChars && (
        <div className="mt-4">
          <div className="text-3xs font-semibold uppercase tracking-wide mb-1.5" style={{ color: "var(--muted)" }}>
            {t("textHeading")}
          </div>
          <form
            onSubmit={(e) => { e.preventDefault(); void submitText(); }}
            className="flex flex-col gap-2"
          >
            <input
              value={textTitle}
              disabled={busy !== null}
              placeholder={t("textTitlePlaceholder")}
              data-testid="add-material-text-title"
              aria-label={t("textTitlePlaceholder")}
              onChange={(e) => { setTextTitle(e.target.value); setTextError(null); }}
              className={`w-full rounded-lg border-2 px-3 py-2 text-sm focus:outline-none transition-colors ${fieldBorderClass(!!textError)}`}
              style={fieldStyle()}
            />
            <TextSourceArea
              value={textBody}
              onChange={(v) => { setTextBody(v); setTextError(null); }}
              maxChars={textMaxChars}
              disabled={busy !== null}
              rows={4}
              error={!!textError}
              testId="add-material-text"
            />
            <div className="flex justify-end">
              <button
                type="submit"
                disabled={busy !== null || !textTitle.trim() || !textBody.trim() || textOver}
                data-testid="add-material-text-submit"
                className="btn-primary px-4 py-2 rounded-lg text-sm font-medium disabled:opacity-50 whitespace-nowrap"
              >
                {busy === "text" ? <Spinner size="sm" color="current" /> : t("textSubmit")}
              </button>
            </div>
          </form>
          {textError && <p className="text-sm mt-2" style={{ color: "var(--error)" }}>{textError}</p>}
        </div>
      )}
    </Modal>
  );
}

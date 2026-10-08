import { useTranslations } from "next-intl";
import Spinner from "@/components/ui/Spinner";
import { GlobeIcon, XIcon } from "@phosphor-icons/react";
import { _fileKind, _getChipIcon } from "../../_utils";
import type { IndexingProgress } from "../../_types";

export function SourceStatus({
  status,
  progress,
}: {
  status: string;
  progress?: IndexingProgress | null;
}) {
  const t = useTranslations("workspace.detail.sources");
  // The spinner stays until the source is really finished.
  const isProcessing =
    status === "pending" || status === "indexing" || (status === "ready" && !!progress);
  if (isProcessing) {
    const stageLabel = progress?.stage
      ? t(`progressStage.${progress.stage}`)
      : null;
    const pageInfo =
      progress?.stage === "ocr" && progress.page && progress.total
        ? ` ${progress.page}/${progress.total}`
        : "";
    return (
      <span className="flex-shrink-0 inline-flex items-center gap-1.5 text-xs text-muted">
        <Spinner size="xs" className="" />
        {stageLabel && (
          <span className="truncate max-w-[8rem]">
            {stageLabel}
            {pageInfo}
          </span>
        )}
      </span>
    );
  }
  if (status === "ready") return null;
  return (
    <span title={t("indexingFailed")} className="flex-shrink-0 inline-flex">
      <XIcon size={12} weight="bold" style={{ color: "var(--error-strong)" }} />
    </span>
  );
}

export function FileIcon({ filename, sourceUrl }: { filename: string; sourceUrl?: string | null }) {
  const t = useTranslations("workspace.detail.sources");
  const kind = _fileKind(filename);
  const isVideo = kind === "video" || kind === "youtube";
  const bg = isVideo ? "#E0E7FF" : kind === "audio" ? "var(--warn-bg)" : kind === "pdf" ? "var(--error-bg)" : kind === "page" ? "var(--success-bg)" : "var(--info-bg)";
  const color = isVideo ? "#4338CA" : kind === "audio" ? "#B45309" : kind === "pdf" ? "var(--error-strong)" : kind === "page" ? "var(--success-strong)" : "var(--info-strong)";
  const Icon = _getChipIcon(filename);
  // A source read from a web page keeps its file icon and gets a globe in the corner.
  const fromWeb = !!sourceUrl && kind !== "youtube" && kind !== "page";
  return (
    <div
      className="relative flex-shrink-0 w-8 h-8 rounded flex items-center justify-center"
      style={{ backgroundColor: bg }}
    >
      <Icon size={16} weight="bold" color={color} />
      {fromWeb && (
        <span
          title={t("fromWebpage")}
          aria-label={t("fromWebpage")}
          className="absolute -bottom-1 -right-1 w-4 h-4 rounded-full flex items-center justify-center"
          style={{ backgroundColor: "var(--background)", border: "1px solid var(--border)" }}
        >
          <GlobeIcon size={10} weight="bold" color="var(--kb)" />
        </span>
      )}
    </div>
  );
}

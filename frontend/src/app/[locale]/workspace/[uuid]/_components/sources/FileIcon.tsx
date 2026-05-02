import { useTranslations } from "next-intl";
import Spinner from "@/components/ui/Spinner";
import { XIcon } from "@phosphor-icons/react";
import { _fileKind, _getChipIcon } from "../../_utils";

export function SourceStatus({ status }: { status: string }) {
  const t = useTranslations("workspace.detail.sources");
  if (status === "pending" || status === "indexing")
    return (
      <Spinner size="xs" className="" />
    );
  if (status === "ready") return null;
  return (
    <span title={t("indexingFailed")} className="flex-shrink-0 inline-flex">
      <XIcon size={12} weight="bold" style={{ color: "var(--error-strong)" }} />
    </span>
  );
}

export function FileIcon({ filename }: { filename: string }) {
  const kind = _fileKind(filename);
  const bg = kind === "video" ? "#E0E7FF" : kind === "audio" ? "var(--warn-bg)" : kind === "pdf" ? "var(--error-bg)" : "var(--info-bg)";
  const color = kind === "video" ? "#4338CA" : kind === "audio" ? "#B45309" : kind === "pdf" ? "var(--error-strong)" : "var(--info-strong)";
  const Icon = _getChipIcon(filename);
  return (
    <div
      className="flex-shrink-0 w-8 h-8 rounded flex items-center justify-center"
      style={{ backgroundColor: bg }}
    >
      <Icon size={16} weight="bold" color={color} />
    </div>
  );
}

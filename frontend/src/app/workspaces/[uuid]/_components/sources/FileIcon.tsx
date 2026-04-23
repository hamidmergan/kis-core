import Spinner from "@/components/ui/Spinner";
import { XIcon } from "@phosphor-icons/react";
import { _fileKind, _getChipIcon } from "../../_utils";

export function SourceStatus({ status }: { status: string }) {
  if (status === "pending" || status === "indexing")
    return (
      <Spinner size="xs" className="" />
    );
  if (status === "ready") return null;
  return (
    <span title="Indizierung fehlgeschlagen" className="flex-shrink-0 inline-flex">
      <XIcon size={12} weight="bold" style={{ color: "#B91C1C" }} />
    </span>
  );
}

export function FileIcon({ filename }: { filename: string }) {
  const kind = _fileKind(filename);
  const bg = kind === "video" ? "#E0E7FF" : kind === "audio" ? "#FEF3C7" : kind === "pdf" ? "#FEE2E2" : "#DBEAFE";
  const color = kind === "video" ? "#4338CA" : kind === "audio" ? "#B45309" : kind === "pdf" ? "#B91C1C" : "#1D4ED8";
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

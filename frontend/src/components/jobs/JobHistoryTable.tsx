"use client";

import { formatDate } from "@/lib/format";
import type { JobHistoryEntry } from "@/hooks/useJobHistory";

/** The last finished runs of one tool, as the same table the admin pages use, a row opens it again. */
export default function JobHistoryTable({
  entries, selectedUuid, disabled, locale, colMaterial, colDate, onSelect,
}: {
  entries: JobHistoryEntry[];
  selectedUuid: string | null;
  disabled?: boolean;
  locale: string;
  colMaterial: string;
  colDate: string;
  onSelect: (jobUuid: string) => void;
}) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm border border-border-soft rounded-xl overflow-hidden">
        <thead className="bg-surface text-xs text-muted uppercase">
          <tr>
            <th className="px-4 py-3 text-left">{colMaterial}</th>
            <th className="px-4 py-3 text-right">{colDate}</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border-soft bg-background">
          {entries.map((e) => (
            <tr
              key={e.job_uuid}
              onClick={() => { if (!disabled) onSelect(e.job_uuid); }}
              tabIndex={disabled ? -1 : 0}
              onKeyDown={(ev) => {
                if (disabled || (ev.key !== "Enter" && ev.key !== " ")) return;
                ev.preventDefault();
                onSelect(e.job_uuid);
              }}
              className={`transition-colors focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-kb ${
                disabled ? "cursor-not-allowed opacity-50" : "cursor-pointer"
              } ${e.job_uuid === selectedUuid ? "bg-kb20" : "hover:bg-surface"}`}
            >
              <td className="max-w-0 w-full px-4 py-3 text-foreground-soft truncate" title={e.original_filename}>
                {e.original_filename}
              </td>
              <td className="px-4 py-3 text-muted-soft text-xs whitespace-nowrap text-right">
                {formatDate(e.created_at, locale)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

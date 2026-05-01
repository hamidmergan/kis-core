import Select from "@/components/ui/Select";

const TOOL_FILTER_OPTIONS = [
  { value: "", label: "Alle Tools" },
  { value: "transcription", label: "Sprache in Text" },
  { value: "translation", label: "Translate" },
  { value: "summary", label: "Summarize" },
  { value: "tts", label: "Text in Sprache" },
  { value: "screencast", label: "Screencast" },
  { value: "image", label: "Image" },
] as const;

interface FilterBarProps {
  q: string;
  toolFilter: string;
  dateFrom: string;
  dateTo: string;
  limit: number;
  total: number;
  hasActiveFilters: boolean;
  onQChange: (v: string) => void;
  onToolFilterChange: (v: string) => void;
  onDateFromChange: (v: string) => void;
  onDateToChange: (v: string) => void;
  onLimitChange: (v: number) => void;
  onReset: () => void;
}


export function FilterBar({
  q, toolFilter, dateFrom, dateTo, limit, total, hasActiveFilters,
  onQChange, onToolFilterChange, onDateFromChange, onDateToChange, onLimitChange, onReset,
}: FilterBarProps) {
  return (
    <div className="mb-4 flex flex-wrap gap-2 items-center">
      <input
        type="text"
        value={q}
        onChange={(e) => onQChange(e.target.value)}
        placeholder="Suche"
        className="flex-1 min-w-[220px] text-sm border border-border rounded-md px-3 py-2 bg-white transition-colors hover:border-kb focus:outline-none focus:ring-2 focus:ring-kb focus:border-kb"
      />
      <Select
        value={toolFilter}
        onChange={onToolFilterChange}
        options={TOOL_FILTER_OPTIONS}
        className="w-44"
      />
      <input
        type="date"
        value={dateFrom}
        onChange={(e) => onDateFromChange(e.target.value)}
        title="Von"
        className="text-sm border border-border rounded-md px-3 py-2 transition-colors hover:border-kb focus:outline-none focus:ring-2 focus:ring-kb focus:border-kb"
      />
      <input
        type="date"
        value={dateTo}
        onChange={(e) => onDateToChange(e.target.value)}
        title="Bis"
        className="text-sm border border-border rounded-md px-3 py-2 transition-colors hover:border-kb focus:outline-none focus:ring-2 focus:ring-kb focus:border-kb"
      />
      <select
        value={limit}
        onChange={(e) => onLimitChange(Number(e.target.value))}
        className="hidden"
      >
        <option value={10}>10 pro Seite</option>
        <option value={25}>25 pro Seite</option>
        <option value={50}>50 pro Seite</option>
      </select>
      <span className="text-xs text-muted-soft whitespace-nowrap">
        {total} Ergebnis{total !== 1 ? "se" : ""}
      </span>
      {hasActiveFilters && (
        <button
          onClick={onReset}
          className="text-xs text-muted-soft hover:text-foreground-soft underline whitespace-nowrap"
        >
          Filter zurücksetzen
        </button>
      )}
    </div>
  );
}

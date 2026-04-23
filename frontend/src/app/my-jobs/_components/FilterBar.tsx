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
      <div className="flex-1 min-w-[220px] flex items-center border border-gray-300 rounded-md bg-white focus-within:ring-2 focus-within:ring-primary">
        <input
          type="text"
          value={q}
          onChange={(e) => onQChange(e.target.value)}
          placeholder="Suche"
          className="flex-1 text-sm px-3 py-2 bg-transparent outline-none min-w-0"
        />
        <div className="w-px h-5 bg-gray-200 shrink-0" />
        <select
          value={toolFilter}
          onChange={(e) => onToolFilterChange(e.target.value)}
          className="text-sm px-2 py-2 bg-transparent outline-none text-gray-500 cursor-pointer appearance-none pr-3"
        >
          <option value="">Alle Tools</option>
          <option value="transcription">Sprache in Text</option>
          <option value="translation">Translate</option>
          <option value="summary">Summarize</option>
          <option value="tts">Text in Sprache</option>
          <option value="screencast">Screencast</option>
          <option value="image">Image</option>
        </select>
      </div>
      <input
        type="date"
        value={dateFrom}
        onChange={(e) => onDateFromChange(e.target.value)}
        title="Von"
        className="text-sm border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-primary"
      />
      <input
        type="date"
        value={dateTo}
        onChange={(e) => onDateToChange(e.target.value)}
        title="Bis"
        className="text-sm border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-primary"
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
      <span className="text-xs text-gray-400 whitespace-nowrap">
        {total} Ergebnis{total !== 1 ? "se" : ""}
      </span>
      {hasActiveFilters && (
        <button
          onClick={onReset}
          className="text-xs text-gray-400 hover:text-gray-700 underline whitespace-nowrap"
        >
          Filter zurücksetzen
        </button>
      )}
    </div>
  );
}

import { useTranslations } from "next-intl";
import Select from "@/components/ui/Select";


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
  const t = useTranslations("myJobs.filter");
  const tt = useTranslations("myJobs.filter.tools");
  const toolOptions = [
    { value: "", label: tt("all") },
    { value: "transcription", label: tt("transcription") },
    { value: "translation", label: tt("translation") },
    { value: "summary", label: tt("summary") },
    { value: "pages", label: tt("pages") },
    { value: "tts", label: tt("tts") },
    { value: "screencast", label: tt("screencast") },
    { value: "podcast", label: tt("podcast") },
    { value: "praesentation", label: tt("praesentation") },
    { value: "image", label: tt("image") },
  ];
  return (
    <div className="mb-4 flex flex-wrap gap-2 items-center">
      <input
        type="text"
        value={q}
        onChange={(e) => onQChange(e.target.value)}
        placeholder={t("search")}
        className="flex-1 min-w-55 text-sm border-2 border-border rounded-md px-3 py-2 bg-background transition-colors hover:border-kb focus:outline-none focus:ring-2 focus:ring-kb focus:border-kb"
      />
      <Select
        value={toolFilter}
        onChange={onToolFilterChange}
        options={toolOptions}
        className="w-44"
      />
      <div className="flex gap-2 min-w-0 max-w-full">
        <div className="flex-1 min-w-0 flex items-center gap-1.5 text-sm border-2 border-border rounded-md px-2.5 py-2 bg-background transition-colors hover:border-kb focus-within:ring-2 focus-within:ring-kb focus-within:border-kb">
          <span className="text-muted-soft whitespace-nowrap">{t("from")}</span>
          <input
            type="date"
            value={dateFrom}
            onChange={(e) => onDateFromChange(e.target.value)}
            className="w-full min-w-0 bg-transparent text-sm focus:outline-none"
          />
        </div>
        <div className="flex-1 min-w-0 flex items-center gap-1.5 text-sm border-2 border-border rounded-md px-2.5 py-2 bg-background transition-colors hover:border-kb focus-within:ring-2 focus-within:ring-kb focus-within:border-kb">
          <span className="text-muted-soft whitespace-nowrap">{t("to")}</span>
          <input
            type="date"
            value={dateTo}
            onChange={(e) => onDateToChange(e.target.value)}
            className="w-full min-w-0 bg-transparent text-sm focus:outline-none"
          />
        </div>
      </div>
      <select
        value={limit}
        onChange={(e) => onLimitChange(Number(e.target.value))}
        className="hidden"
      >
        <option value={10}>{t("perPage", { n: 10 })}</option>
        <option value={25}>{t("perPage", { n: 25 })}</option>
        <option value={50}>{t("perPage", { n: 50 })}</option>
      </select>
      <span className="text-xs text-muted-soft whitespace-nowrap">
        {t("results", { count: total })}
      </span>
      {hasActiveFilters && (
        <button
          onClick={onReset}
          className="text-xs text-muted-soft hover:text-foreground-soft underline whitespace-nowrap"
        >
          {t("reset")}
        </button>
      )}
    </div>
  );
}

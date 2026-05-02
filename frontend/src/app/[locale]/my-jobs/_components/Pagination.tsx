interface PaginationProps {
  total: number;
  offset: number;
  limit: number;
  onOffsetChange: (offset: number) => void;
}


export function Pagination({ total, offset, limit, onOffsetChange }: PaginationProps) {
  const totalPages = Math.max(1, Math.ceil(total / limit));
  const currentPage = Math.floor(offset / limit) + 1;

  if (totalPages <= 1) return null;

  const half = 3;
  let start = Math.max(1, currentPage - half);
  const end = Math.min(totalPages, start + 6);
  start = Math.max(1, end - 6);
  const pageNumbers = Array.from({ length: end - start + 1 }, (_, i) => start + i);

  return (
    <div className="mt-4 flex items-center justify-center gap-1 pt-2">
      <button
        onClick={() => onOffsetChange(Math.max(0, offset - limit))}
        disabled={currentPage === 1}
        className="px-3 py-1.5 text-sm border-2 border-border rounded-md transition-colors disabled:opacity-40 enabled:hover:border-[var(--kb)] enabled:hover:text-[var(--kb)]"
      >
        ‹
      </button>
      {pageNumbers.map((p) => (
        <button
          key={p}
          onClick={() => onOffsetChange((p - 1) * limit)}
          className={`px-3 py-1.5 text-sm border-2 rounded-md transition-colors ${
            p === currentPage
              ? "bg-kb text-white border-kb"
              : "border-border hover:border-[var(--kb)] hover:text-[var(--kb)]"
          }`}
        >
          {p}
        </button>
      ))}
      <button
        onClick={() => onOffsetChange(Math.min((totalPages - 1) * limit, offset + limit))}
        disabled={currentPage === totalPages}
        className="px-3 py-1.5 text-sm border-2 border-border rounded-md transition-colors disabled:opacity-40 enabled:hover:border-[var(--kb)] enabled:hover:text-[var(--kb)]"
      >
        ›
      </button>
    </div>
  );
}

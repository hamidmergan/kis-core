"use client";

import { pageWindow } from "./pageWindow";

/** Previous, page numbers and next below an admin table, hidden for a single page. */
export default function Pager({ total, limit, offset, onOffset }: {
  total: number;
  limit: number;
  offset: number;
  onOffset: (offset: number) => void;
}) {
  const totalPages = Math.max(1, Math.ceil(total / limit));
  const currentPage = Math.floor(offset / limit) + 1;
  if (totalPages <= 1) return null;

  return (
    <div className="flex items-center justify-center gap-1 pt-2">
      <button
        onClick={() => onOffset(Math.max(0, offset - limit))}
        disabled={currentPage === 1}
        className="px-3 py-1.5 text-sm border-2 border-border rounded-md transition-colors disabled:opacity-40 enabled:hover:border-[var(--kb)] enabled:hover:text-[var(--kb)]"
      >
        ‹
      </button>
      {pageWindow(currentPage, totalPages).map((page) => (
        <button
          key={page}
          onClick={() => onOffset((page - 1) * limit)}
          className={`px-3 py-1.5 text-sm border-2 rounded-md transition-colors ${
            page === currentPage
              ? "bg-kb text-white border-kb"
              : "border-border hover:border-[var(--kb)] hover:text-[var(--kb)]"
          }`}
        >
          {page}
        </button>
      ))}
      <button
        onClick={() => onOffset(offset + limit)}
        disabled={currentPage === totalPages}
        className="px-3 py-1.5 text-sm border-2 border-border rounded-md transition-colors disabled:opacity-40 enabled:hover:border-[var(--kb)] enabled:hover:text-[var(--kb)]"
      >
        ›
      </button>
    </div>
  );
}

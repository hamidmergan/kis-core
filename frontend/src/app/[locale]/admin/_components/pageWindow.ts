/** The page numbers a pager shows: at most seven, centred on the current page. */
export function pageWindow(currentPage: number, totalPages: number): number[] {
  let start = Math.max(1, currentPage - 3);
  const end = Math.min(totalPages, start + 6);
  start = Math.max(1, end - 6);
  const pages: number[] = [];
  for (let page = start; page <= end; page++) pages.push(page);
  return pages;
}

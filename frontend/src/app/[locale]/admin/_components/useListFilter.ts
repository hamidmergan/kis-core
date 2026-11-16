import { useEffect, useMemo, useState } from "react";

/** Search text, date range and paging of an admin list, with the query string for the request. */
export function useListFilter() {
  const [q, setQ] = useState("");
  const [debouncedQ, setDebouncedQ] = useState("");
  const [limit, setLimit] = useState(50);
  const [offset, setOffset] = useState(0);
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");

  useEffect(() => {
    const id = setTimeout(() => setDebouncedQ(q), 350);
    return () => clearTimeout(id);
  }, [q]);

  useEffect(() => {
    setOffset(0);
  }, [debouncedQ, limit, dateFrom, dateTo]);

  const query = useMemo(() => {
    const params = new URLSearchParams({
      limit: String(limit),
      offset: String(offset),
      q: debouncedQ,
    });
    if (dateFrom) params.set("date_from", dateFrom);
    if (dateTo) params.set("date_to", dateTo);
    return params.toString();
  }, [limit, offset, debouncedQ, dateFrom, dateTo]);

  return { q, setQ, limit, setLimit, offset, setOffset, dateFrom, setDateFrom, dateTo, setDateTo, query };
}

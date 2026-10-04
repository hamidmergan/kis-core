async function request<T>(path: string): Promise<T> {
  const res = await fetch(`/api${path}`, { credentials: "include", cache: "no-store" });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return (await res.json()) as T;
}

export const campusApi = {
  map: () => request<{ map_url: string }>("/campus/map"),
};

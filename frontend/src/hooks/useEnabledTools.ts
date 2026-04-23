"use client";

import { useEffect, useState } from "react";

interface Tool {
  key: string;
  enabled: boolean;
}

export function useEnabledTools() {
  const [tools, setTools] = useState<Tool[] | null>(null);

  useEffect(() => {
    fetch("/api/admin/tools", { credentials: "include" })
      .then((r) => r.json())
      .then((d) => setTools(d.tools ?? []))
      .catch(() => setTools([]));
  }, []);

  const loaded = tools !== null;
  const isToolEnabled = (key: string) => {
    if (!tools) return true;
    const tool = tools.find((t) => t.key === key);
    return !tool || tool.enabled;
  };

  return { tools, loaded, isToolEnabled };
}

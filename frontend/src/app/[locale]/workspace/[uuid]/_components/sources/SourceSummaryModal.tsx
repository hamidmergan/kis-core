"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { useTranslations } from "next-intl";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import Modal from "@/components/ui/Modal";
import Spinner from "@/components/ui/Spinner";
import { api } from "@/lib/api";
import { KATEX_OPTIONS } from "../../_constants";
import type { Source } from "../../_types";

/** What a material is about, fetched only when somebody opens it. */
export function SourceSummaryModal({ source, onClose }: {
  source: Source | null;
  onClose: () => void;
}) {
  const t = useTranslations("workspace.detail.sources.summary");
  const params = useParams();
  const workspaceUuid = String(params?.uuid ?? "");
  const [text, setText] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    if (!source) return;
    setText(null);
    setFailed(false);
    let abgelaufen = false;
    (async () => {
      try {
        const res = await api.fetch(
          `/api/ai-assistant/workspaces/${workspaceUuid}/sources/${source.uuid}/summary`);
        const data = res.ok ? await res.json() : null;
        if (!abgelaufen) {
          if (data) setText(data.summary || "");
          else setFailed(true);
        }
      } catch {
        if (!abgelaufen) setFailed(true);
      }
    })();
    return () => { abgelaufen = true; };
  }, [source, workspaceUuid]);

  return (
    <Modal open={Boolean(source)} onClose={onClose} title={source?.filename ?? t("title")} size="lg">
      <div className="space-y-3">
        {text === null && !failed && (
          <div className="flex items-center gap-2 py-6 justify-center">
            <Spinner size="sm" />
          </div>
        )}
        {failed && (
          <p className="text-sm" style={{ color: "var(--error-strong)" }}>{t("failed")}</p>
        )}
        {text !== null && text.trim() === "" && (
          <p className="text-sm" style={{ color: "var(--muted-foreground)" }}>{t("empty")}</p>
        )}
        {text !== null && text.trim() !== "" && (
          <div className="text-sm leading-relaxed" style={{ color: "var(--foreground)" }}>
              <ReactMarkdown
                remarkPlugins={[remarkGfm, remarkMath]}
                rehypePlugins={[[rehypeKatex, KATEX_OPTIONS]]}
                components={{
                  p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
                  ul: ({ children }) => <ul className="list-disc pl-4 mb-2 space-y-1">{children}</ul>,
                  ol: ({ children }) => <ol className="list-decimal pl-4 mb-2 space-y-1">{children}</ol>,
                  strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
                }}
              >
                {text}
              </ReactMarkdown>
          </div>
        )}
      </div>
    </Modal>
  );
}

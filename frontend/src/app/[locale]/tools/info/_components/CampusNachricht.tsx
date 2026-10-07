"use client";

import { memo, useState } from "react";
import { useTranslations } from "next-intl";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Check, Copy } from "@phosphor-icons/react";
import OrtKarte from "@/components/campus/OrtKarte";
import QuellenKarten from "./QuellenKarten";
import WartezeileCampus from "./WartezeileCampus";
import type { CampusNachricht as Nachricht } from "../_types";

function CampusNachrichtInner({
  msg,
  mapUrl,
  isLatest,
}: {
  msg: Nachricht;
  mapUrl: string;
  isLatest: boolean;
}) {
  const t = useTranslations("tools.campus");
  const [copied, setCopied] = useState(false);
  const isUser = msg.role === "user";
  const waiting = !isUser && msg.streaming && !msg.content;

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(msg.content);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // Without clipboard access the button simply does nothing.
    }
  };

  return (
    <div className={`flex ${isUser ? "justify-end group" : "justify-start mt-3"}`} data-testid={isUser ? "user-message" : "assistant-message"}>
      <div className={`flex gap-3 ${isUser ? "max-w-[85%] sm:max-w-[75%]" : "w-full"}`}>
        <div className="min-w-0 flex-1">
          {waiting ? (
            <WartezeileCampus metaArrived={!!msg.metaArrived} />
          ) : (
            <div
              className={`px-4 py-2 rounded-2xl text-base leading-snug break-words ${isUser ? "" : "w-full sm:w-[90%]"} ${!isUser && msg.streaming && msg.content ? "stream-cursor" : ""}`}
              style={
                isUser
                  ? { backgroundColor: "var(--kb)", color: "white", borderBottomRightRadius: 6, whiteSpace: "pre-wrap", overflowWrap: "break-word" }
                  : { color: "var(--foreground)", overflowWrap: "break-word" }
              }
            >
              {isUser ? (
                msg.content
              ) : msg.failed ? (
                <span className="text-sm italic" style={{ color: "var(--muted)" }}>{msg.content || t("genericError")}</span>
              ) : (
                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}
                  components={{
                    p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
                    ul: ({ children }) => <ul className="list-disc pl-4 mb-2 space-y-0.5">{children}</ul>,
                    ol: ({ children }) => <ol className="list-decimal pl-4 mb-2 space-y-0.5">{children}</ol>,
                    li: ({ children }) => <li className="leading-snug">{children}</li>,
                    strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
                    h1: ({ children }) => <p className="font-semibold mb-1">{children}</p>,
                    h2: ({ children }) => <p className="font-semibold mb-1">{children}</p>,
                    h3: ({ children }) => <p className="font-medium mb-1">{children}</p>,
                    a: ({ href, children }) => (
                      <a href={href} target="_blank" rel="noopener noreferrer" className="underline">{children}</a>
                    ),
                    table: ({ children }) => <div className="overflow-x-auto my-2"><table className="w-full text-sm border-collapse">{children}</table></div>,
                    th: ({ children }) => <th className="text-left px-2 py-1 font-semibold">{children}</th>,
                    td: ({ children }) => <td className="px-2 py-1 border-t border-current/10">{children}</td>,
                  }}
                >
                  {msg.content || t("noAnswer")}
                </ReactMarkdown>
              )}
            </div>
          )}

          {isUser && (
            <div className="flex justify-end mt-1">
              <button
                type="button"
                onClick={copy}
                title={t("copy")}
                className="w-7 h-7 flex items-center justify-center rounded-full btn-icon [@media(hover:hover)]:opacity-0 [@media(hover:hover)]:group-hover:opacity-100"
              >
                {copied ? <Check size={14} weight="bold" /> : <Copy size={14} weight="bold" />}
              </button>
            </div>
          )}

          {!isUser && !msg.streaming && !msg.failed && (
            <>
              {(msg.places.length > 0 || msg.sources.length > 0 || msg.content) && (
                <div className="mt-2 flex flex-wrap items-center gap-1.5">
                  {msg.content && (
                    <button type="button" onClick={copy} title={t("copy")} className="w-7 h-7 flex items-center justify-center rounded-full btn-icon">
                      {copied ? <Check size={14} weight="bold" /> : <Copy size={14} weight="bold" />}
                    </button>
                  )}
                  {msg.places.map((ort) => <OrtKarte key={ort.id} ort={ort} mapUrl={mapUrl} />)}
                  <QuellenKarten quellen={msg.sources} />
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

const CampusNachricht = memo(CampusNachrichtInner);
export default CampusNachricht;

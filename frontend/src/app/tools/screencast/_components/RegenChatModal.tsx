"use client";

import { useEffect, useRef, useState } from "react";
import Spinner from "@/components/ui/Spinner";
import { api } from "@/lib/api";

const MAX_REGEN_TEXTAREA_HEIGHT = 480;

function RegenTextarea({
  value,
  onChange,
  className,
  style,
}: {
  value: string;
  onChange: (v: string) => void;
  className: string;
  style?: React.CSSProperties;
}) {
  const ref = useRef<HTMLTextAreaElement>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, MAX_REGEN_TEXTAREA_HEIGHT) + "px";
  }, [value]);
  return (
    <textarea
      ref={ref}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      rows={1}
      className={className}
      style={style}
    />
  );
}

export type RegenApplyMode = "replace-selection" | "insert-before" | "insert-after" | "replace-all";

interface RegenChatModalProps {
  slideIndex: number;
  slideExtractedText: string;
  currentScript: string;
  anchorText: string;
  targetLang: string;
  onApply: (mode: RegenApplyMode, content: string) => void;
  onClose: () => void;
}

export default function RegenChatModal({
  slideIndex,
  slideExtractedText,
  currentScript,
  anchorText,
  targetLang,
  onApply,
  onClose,
}: RegenChatModalProps) {
  const [prompt, setPrompt] = useState("");
  const [messages, setMessages] = useState<{ role: "user" | "assistant"; content: string }[]>([]);
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  async function runRegen() {
    const userText = prompt.trim();
    if (!userText) return;
    const newMessages: { role: "user" | "assistant"; content: string }[] = [
      ...messages,
      { role: "user", content: userText },
    ];
    setMessages(newMessages);
    setPrompt("");
    setLoading(true);
    try {
      const result = await api.postJson<{ script: string }>("/api/screencast/regenerate-slide-script", {
        slide_text: slideExtractedText,
        current_script: currentScript,
        messages: newMessages,
        selected_text: anchorText || null,
        target_lang: targetLang,
      });
      setMessages([...newMessages, { role: "assistant", content: result.script }]);
    } catch {
      setMessages([...newMessages, { role: "assistant", content: "Fehler beim Generieren." }]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      <div className="fixed inset-0 z-40" />
      <div
        className={`fixed z-50 shadow-2xl flex flex-col overflow-hidden sm:inset-auto sm:top-16 sm:bottom-6 sm:right-6 sm:w-[380px] sm:rounded-2xl ${messages.length > 0 ? "inset-0 rounded-none" : "inset-x-0 bottom-0 rounded-t-2xl max-h-[60vh]"}`}
        style={{ backgroundColor: "var(--bg)" }}
      >
        <div
          className="flex items-center justify-between px-4 py-3"
          style={{ borderBottom: "1px solid var(--border)" }}
        >
          <div className="flex items-center gap-2">
            <div
              className="w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold text-white flex-shrink-0"
              style={{ backgroundColor: "var(--kb)" }}
            >
              KI
            </div>
            <span className="text-sm font-semibold" style={{ color: "var(--text)" }}>
              KI-Assistent · Folie {slideIndex + 1}
            </span>
          </div>
          <button
            onClick={onClose}
            className="w-7 h-7 flex items-center justify-center rounded-full hover:opacity-70 transition-opacity"
            style={{ backgroundColor: "var(--border)", color: "var(--muted)" }}
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-4 py-3 space-y-4 min-h-0">
          {anchorText && (
            <div className="flex justify-center">
              <div
                className="w-full rounded-xl px-3 py-1.5 text-xs italic"
                style={{
                  backgroundColor: "rgba(var(--kb-rgb),0.06)",
                  color: "var(--text)",
                  border: "1px solid var(--border)",
                }}
              >
                <span style={{ color: "var(--kb)" }}>✦</span> „{anchorText}"
              </div>
            </div>
          )}

          {messages.map((msg, idx) => {
            const isUser = msg.role === "user";
            const isLastAssistant = !isUser && idx === messages.length - 1;
            return (
              <div key={idx} className={`flex flex-col gap-1.5 ${isUser ? "items-end" : "items-start"}`}>
                {!isUser && (
                  <div className="flex items-center gap-2 mb-0.5">
                    <div
                      className="w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold text-white flex-shrink-0"
                      style={{ backgroundColor: "var(--kb)" }}
                    >
                      KI
                    </div>
                    <span className="text-[11px] font-medium" style={{ color: "var(--muted)" }}>
                      KI-Assistent
                    </span>
                  </div>
                )}
                <div
                  className={`${isUser ? "max-w-[85%]" : "max-w-[96%]"} space-y-2 ${isUser ? "items-end" : "items-start"} flex flex-col`}
                >
                  {isUser ? (
                    <div
                      className="text-sm px-4 py-3 rounded-2xl leading-relaxed"
                      style={{
                        backgroundColor: "var(--kb)",
                        color: "white",
                        borderBottomRightRadius: 6,
                        whiteSpace: "pre-wrap",
                      }}
                    >
                      {msg.content}
                    </div>
                  ) : (
                    <>
                      <RegenTextarea
                        value={msg.content}
                        onChange={(v) =>
                          setMessages(messages.map((m, i) => (i === idx ? { ...m, content: v } : m)))
                        }
                        className="text-sm rounded-2xl px-4 py-3 focus:outline-none focus:ring-2 focus:ring-primary/30 resize-none leading-relaxed w-full overflow-y-auto"
                        style={{
                          backgroundColor: "var(--surface)",
                          color: "var(--text)",
                          border: "1px solid var(--border)",
                          borderTopLeftRadius: 6,
                        }}
                      />
                      {isLastAssistant && (
                        <div className="flex flex-wrap gap-1.5">
                          {anchorText ? (
                            <>
                              <button
                                onClick={() => onApply("replace-selection", msg.content)}
                                className="px-3 py-1 text-xs font-medium rounded-full hover:opacity-80 transition-opacity"
                                style={{ backgroundColor: "rgba(var(--kb-rgb),0.08)", color: "var(--kb)" }}
                              >
                                Markierung ersetzen
                              </button>
                              <button
                                onClick={() => onApply("insert-before", msg.content)}
                                className="px-3 py-1 text-xs font-medium rounded-full hover:opacity-80 transition-opacity"
                                style={{ backgroundColor: "rgba(var(--kb-rgb),0.08)", color: "var(--kb)" }}
                              >
                                Davor
                              </button>
                              <button
                                onClick={() => onApply("insert-after", msg.content)}
                                className="px-3 py-1 text-xs font-medium rounded-full hover:opacity-80 transition-opacity"
                                style={{ backgroundColor: "rgba(var(--kb-rgb),0.08)", color: "var(--kb)" }}
                              >
                                Danach
                              </button>
                              <button
                                onClick={() => onApply("replace-all", msg.content)}
                                className="px-3 py-1 text-xs font-medium rounded-full hover:opacity-80 transition-opacity"
                                style={{ backgroundColor: "rgba(var(--kb-rgb),0.05)", color: "var(--muted)" }}
                              >
                                Ganzes Skript
                              </button>
                            </>
                          ) : (
                            <button
                              onClick={() => onApply("replace-all", msg.content)}
                              className="px-3 py-1 text-xs font-medium rounded-full hover:opacity-80 transition-opacity"
                              style={{ backgroundColor: "rgba(var(--kb-rgb),0.08)", color: "var(--kb)" }}
                            >
                              Ersetzen
                            </button>
                          )}
                        </div>
                      )}
                    </>
                  )}
                </div>
              </div>
            );
          })}

          {loading && (
            <div className="flex items-start gap-2">
              <div
                className="w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold text-white flex-shrink-0"
                style={{ backgroundColor: "var(--kb)" }}
              >
                KI
              </div>
              <div
                className="px-4 py-3 rounded-2xl text-sm"
                style={{
                  backgroundColor: "var(--surface)",
                  border: "1px solid var(--border)",
                  borderTopLeftRadius: 6,
                }}
              >
                <span className="inline-flex items-center gap-2">
                  <span className="inline-flex gap-1">
                    {[0, 1, 2].map((n) => (
                      <span
                        key={n}
                        className="inline-block w-1.5 h-1.5 rounded-full animate-bounce"
                        style={{ backgroundColor: "var(--muted)", animationDelay: `${n * 0.15}s` }}
                      />
                    ))}
                  </span>
                  <span className="text-xs" style={{ color: "var(--muted)" }}>
                    Denkt nach…
                  </span>
                </span>
              </div>
            </div>
          )}

          <div ref={bottomRef} />
        </div>

        <div className="px-4 pt-4 pb-3" style={{ borderTop: "1px solid var(--border)" }}>
          <div
            className="flex items-center gap-2 rounded-2xl px-4 py-3"
            style={{ backgroundColor: "var(--surface)", border: "1px solid var(--border)" }}
          >
            <textarea
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  if (!loading) runRegen();
                }
              }}
              rows={1}
              placeholder="Text eingeben…"
              autoFocus
              className="flex-1 text-sm resize-none focus:outline-none disabled:opacity-50 bg-transparent"
              style={{ color: "var(--text)", maxHeight: 160, overflowY: "auto" }}
            />
            <button
              onClick={runRegen}
              disabled={loading}
              className="flex-shrink-0 w-9 h-9 flex items-center justify-center rounded-xl text-white disabled:opacity-40 transition-opacity hover:opacity-85"
              style={{ backgroundColor: "var(--kb)" }}
            >
              {loading ? (
                <Spinner size="sm" color="current" />
              ) : (
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 12h14M12 5l7 7-7 7" />
                </svg>
              )}
            </button>
          </div>
        </div>
      </div>
    </>
  );
}

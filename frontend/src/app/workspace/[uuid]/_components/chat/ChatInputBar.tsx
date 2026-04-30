import React, { useCallback, useEffect, useRef, useState } from "react";
import { PaperPlaneRight, X } from "@phosphor-icons/react";


interface ChatInputBarProps {
  loading: boolean;
  activeSourceIds: string[];
  onSend: (value: string) => void;
  externalTextareaRef?: React.RefObject<HTMLTextAreaElement | null>;
  registerSetInput?: (setter: ((v: string) => void) | null) => void;
}


export function ChatInputBar({
  loading, activeSourceIds, onSend, externalTextareaRef, registerSetInput,
}: ChatInputBarProps) {
  const [input, setInput] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const textareaCallbackRef = useCallback((el: HTMLTextAreaElement | null) => {
    (textareaRef as React.MutableRefObject<HTMLTextAreaElement | null>).current = el;
    if (externalTextareaRef) (externalTextareaRef as React.MutableRefObject<HTMLTextAreaElement | null>).current = el;
  }, [externalTextareaRef]);

  useEffect(() => {
    registerSetInput?.(setInput);
    return () => registerSetInput?.(null);
  }, [registerSetInput]);

  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 160) + "px";
  }, [input]);

  const submit = useCallback(() => {
    const value = input;
    if (!value.trim()) return;
    onSend(value);
    setInput("");
  }, [input, onSend]);

  return (
    <div
      className="flex-shrink-0 px-6 pt-2 pb-0"
      style={{ borderTop: "1px solid var(--border)" }}
    >
      <div className="mx-auto w-full" style={{ maxWidth: 720 }}>
        <div className="flex justify-end px-1 mb-1">
          <span className="text-xs leading-none" style={{ color: "var(--muted)" }}>
            {activeSourceIds.length} {activeSourceIds.length === 1 ? "Quelle" : "Quellen"} aktiv
          </span>
        </div>
        <div
          className="flex items-center gap-2 rounded-2xl px-4 py-3"
          style={{ backgroundColor: "var(--surface)", border: "1px solid var(--border)" }}
        >
          <textarea
            ref={textareaCallbackRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); submit(); }
            }}
            placeholder="Text eingeben…"
            rows={1}
            disabled={loading}
            className="flex-1 text-base resize-none focus:outline-none disabled:opacity-50 bg-transparent"
            style={{ color: "var(--foreground)", maxHeight: 160, overflowY: "auto" }}
          />
          {input && (
            <button
              type="button"
              onClick={() => { setInput(""); textareaRef.current?.focus(); }}
              className="flex-shrink-0 w-6 h-6 flex items-center justify-center rounded-full btn-icon"
              
              title="Eingabe löschen"
            >
              <X size={14} weight="bold" />
            </button>
          )}
          <button
            type="button"
            onClick={submit}
            disabled={loading || !input.trim() || activeSourceIds.length === 0}
            className="btn-fill-accent flex-shrink-0 w-9 h-9 flex items-center justify-center rounded-xl disabled:opacity-40 transition-colors"
            title="Senden"
          >
            <PaperPlaneRight size={16} weight="bold" />
          </button>
        </div>
      </div>
    </div>
  );
}

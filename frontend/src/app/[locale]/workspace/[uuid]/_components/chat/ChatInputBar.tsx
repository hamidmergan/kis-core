import React, { useCallback, useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { PaperPlaneRight, Stop, X } from "@phosphor-icons/react";


interface ChatInputBarProps {
  loading: boolean;
  /** Tutor chat only: shows the "N sources active" line and gates sending on it.
   *  Omitted by callers without sources, e.g. the language diagnosis. */
  activeSourceIds?: string[];
  onSend: (value: string) => void;
  onStop?: () => void;
  externalTextareaRef?: React.RefObject<HTMLTextAreaElement | null>;
  registerSetInput?: (setter: ((v: string) => void) | null) => void;
  /** Defaults to the tutor-chat placeholder. */
  placeholder?: string;
  /** Blocks typing entirely, e.g. while a turn is still being answered. */
  disabled?: boolean;
  /** Hard cap on one message. Mirror the caller's backend limit. */
  maxLength?: number;
}


export function ChatInputBar({
  loading, activeSourceIds, onSend, onStop, externalTextareaRef, registerSetInput,
  placeholder, disabled = false, maxLength = 8000,
}: ChatInputBarProps) {
  const t = useTranslations("workspace.detail.chat");
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
      <div className="mx-auto w-full" style={{ maxWidth: 920 }}>
        {activeSourceIds && (
          <div className="flex justify-end px-1 mb-1">
            <span className="text-xs leading-none" style={{ color: "var(--muted)" }}>
              {t("sourcesActive", { n: activeSourceIds.length })}
            </span>
          </div>
        )}
        <div
          className="flex items-center gap-2 rounded-2xl px-4 py-3"
          style={{ backgroundColor: "var(--surface)", border: "1px solid var(--border)" }}
        >
          <textarea
            ref={textareaCallbackRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); if (!loading && !disabled) submit(); }
            }}
            placeholder={placeholder ?? t("inputPlaceholder")}
            disabled={disabled}
            // Hard cap mirrors the caller's backend limit (chat: AIA_QUESTION_MAX_CHARS)
            // so an oversized paste is bounced here instead of coming back as a 422.
            maxLength={maxLength}
            rows={1}
            className="flex-1 text-base resize-none focus:outline-none disabled:opacity-50 bg-transparent"
            style={{ color: "var(--foreground)", maxHeight: 160, overflowY: "auto" }}
          />
          {input && (
            <button
              type="button"
              onClick={() => { setInput(""); textareaRef.current?.focus(); }}
              className="flex-shrink-0 w-6 h-6 flex items-center justify-center rounded-full btn-icon"
              
              title={t("clearInput")}
            >
              <X size={14} weight="bold" />
            </button>
          )}
          {loading && onStop ? (
            <button
              type="button"
              onClick={onStop}
              className="btn-fill-accent flex-shrink-0 w-9 h-9 flex items-center justify-center rounded-xl transition-colors"
              title={t("stop")}
            >
              <Stop size={16} weight="bold" />
            </button>
          ) : (
            <button
              type="button"
              onClick={submit}
              disabled={loading || disabled || !input.trim() || activeSourceIds?.length === 0}
              className="btn-fill-accent flex-shrink-0 w-9 h-9 flex items-center justify-center rounded-xl disabled:opacity-40 transition-colors"
              title={t("send")}
            >
              <PaperPlaneRight size={16} weight="bold" />
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

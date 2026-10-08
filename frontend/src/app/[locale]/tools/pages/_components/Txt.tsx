"use client";

import { createContext, createElement, memo, useContext, useEffect, useLayoutEffect, useRef } from "react";
import { useTranslations } from "next-intl";

/** What every editable text needs from the editor, a reader gets the inert default. */
export interface EditContext {
  editing: boolean;
  /** Counts every change of the page, so a text left showing an undone value is set again. */
  rev: number;
  commit: (path: string, value: string) => void;
  typing: () => void;
}

export const EditCtx = createContext<EditContext>({ editing: false, rev: 0, commit: () => {}, typing: () => {} });

interface TxtProps {
  path: string;
  value: string | undefined;
  as?: keyof React.JSX.IntrinsicElements;
  className?: string;
  max: number;
  /** Table cells stay, the trash removes whole rows instead. */
  keep?: boolean;
}

/**
 * One text of the page. React only sets it when the stored value changes, so typing never
 * fights a re-render; the text reaches the page on blur, one undo step per field.
 */
export const Txt = memo(function Txt({ path, value, as = "span", className, max, keep }: TxtProps) {
  const ctx = useContext(EditCtx);
  const t = useTranslations("tools.pages");
  const ref = useRef<HTMLElement>(null);

  useLayoutEffect(() => {
    const el = ref.current;
    if (el && el.textContent !== (value ?? "")) el.textContent = value ?? "";
  }, [value, ctx.editing, ctx.rev]);

  // The limit is held while typing, a paste is cut to what still fits.
  useEffect(() => {
    const el = ref.current;
    if (!el || !ctx.editing) return;
    const guard = (e: InputEvent) => {
      if (!e.inputType.startsWith("insert")) return;
      const add = (e.data ?? e.dataTransfer?.getData("text/plain") ?? " ").length;
      const chosen = window.getSelection()?.toString().length ?? 0;
      if ((el.textContent ?? "").length - chosen + add > max) {
        e.preventDefault();
        el.classList.add("ed-full");
        el.title = t("maxChars", { max });
        window.setTimeout(() => el.classList.remove("ed-full"), 700);
      }
    };
    const paste = (e: ClipboardEvent) => {
      e.preventDefault();
      const room = max - (el.textContent ?? "").length + (window.getSelection()?.toString().length ?? 0);
      const text = (e.clipboardData?.getData("text/plain") ?? "").replace(/\s+/g, " ").slice(0, Math.max(0, room));
      document.execCommand("insertText", false, text);
    };
    el.addEventListener("beforeinput", guard);
    el.addEventListener("paste", paste);
    return () => {
      el.removeEventListener("beforeinput", guard);
      el.removeEventListener("paste", paste);
    };
  }, [ctx.editing, max, t]);

  if (!value) return null;
  return createElement(as, {
    ref,
    className,
    "data-p": path,
    "data-keep": keep ? "" : undefined,
    contentEditable: ctx.editing ? true : undefined,
    suppressContentEditableWarning: true,
    spellCheck: ctx.editing ? true : undefined,
    onInput: ctx.editing ? ctx.typing : undefined,
    onBlur: ctx.editing
      ? (e: React.FocusEvent<HTMLElement>) => {
          // Always handed over, an unchanged text ends the typing state without a new step.
          ctx.commit(path, (e.currentTarget.textContent ?? "").replace(/\s+/g, " ").trim());
        }
      : undefined,
    onKeyDown: ctx.editing
      ? (e: React.KeyboardEvent<HTMLElement>) => {
          if (e.key === "Enter") {
            e.preventDefault();
            e.currentTarget.blur();
          }
        }
      : undefined,
  });
});

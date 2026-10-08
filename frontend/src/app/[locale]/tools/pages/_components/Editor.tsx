"use client";

import { useCallback, useEffect, useMemo, useReducer, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useTranslations } from "next-intl";
import { ShareNetwork, Trash } from "@phosphor-icons/react";
import Tabs from "@/components/ui/Tabs";
import Spinner from "@/components/ui/Spinner";
import ScrollTopButton from "@/app/[locale]/_components/landing/ScrollTopButton";
import * as api from "../_lib/api";
import { clone, deleteAt, dropEmptyBlocks, setAt } from "../_lib/paths";
import type { Limits, OwnPage, Page } from "../_lib/types";
import PageBar from "./PageBar";
import PageView from "./PageView";
import { ShareModal } from "./Sharing";
import { EditCtx } from "./Txt";

// Undo keeps this many steps, typing in one field is one step.
const UNDO_STEPS = 20;

interface History {
  rev: number;
  page: Page;
  past: Page[];
  future: Page[];
}

type Action =
  | { type: "change"; fn: (p: Page) => void }
  | { type: "undo" }
  | { type: "redo" }
  | { type: "replace"; page: Page };

function reducer(h: History, a: Action): History {
  switch (a.type) {
    case "change": {
      const next = clone(h.page);
      a.fn(next);
      if (JSON.stringify(next) === JSON.stringify(h.page)) return h;
      return { rev: h.rev + 1, page: next, past: [...h.past, h.page].slice(-UNDO_STEPS), future: [] };
    }
    case "undo":
      if (!h.past.length) return h;
      return { rev: h.rev + 1, page: h.past[h.past.length - 1], past: h.past.slice(0, -1), future: [h.page, ...h.future] };
    case "redo":
      if (!h.future.length) return h;
      return { rev: h.rev + 1, page: h.future[0], past: [...h.past, h.page], future: h.future.slice(1) };
    case "replace":
      return { ...h, rev: h.rev + 1, page: a.page };
  }
}

/** Compares two pages by content, the save stamp is no change. */
const same = (a: Page, b: Page) => JSON.stringify({ ...a, saved_at: 0 }) === JSON.stringify({ ...b, saved_at: 0 });

export default function Editor({ uuid }: { uuid: string }) {
  const t = useTranslations("tools.pages");
  const [loaded, setLoaded] = useState<OwnPage | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  useEffect(() => {
    api.getPage(uuid).then(setLoaded).catch((e: Error) => setLoadError(e.message || t("loadFailed")));
  }, [uuid, t]);

  if (loadError) {
    return (
      <>
        <PageBar back="/tools/pages" backLabel={t("back")} />
        <p className="max-w-xl mx-auto mt-24 px-4 text-center text-sm" style={{ color: "var(--muted)" }} role="alert">{loadError}</p>
      </>
    );
  }
  if (!loaded) {
    return (
      <div className="flex items-center justify-center min-h-[50vh]"><Spinner size="lg" /></div>
    );
  }
  return <Loaded uuid={uuid} data={loaded} />;
}

function Loaded({ uuid, data }: { uuid: string; data: OwnPage }) {
  const t = useTranslations("tools.pages");
  const [h, dispatch] = useReducer(reducer, { rev: 0, page: data.page, past: [], future: [] });
  const [saved, setSaved] = useState<Page>(data.page);
  const [editing, setEditing] = useState(false);
  const [typing, setTyping] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [share, setShare] = useState({ shared: data.shared, code: data.code });
  const [shareOpen, setShareOpen] = useState(false);
  const [shareBusy, setShareBusy] = useState(false);
  const limits: Limits = data.limits;
  const dirty = typing || !same(h.page, saved);

  const commit = useCallback((path: string, value: string) => {
    setTyping(false);
    dispatch({
      type: "change",
      fn: (p) => {
        if (value) setAt(p, path, value);
        else {
          deleteAt(p, path);
          dropEmptyBlocks(p);
        }
      },
    });
  }, []);
  const ctx = useMemo(() => ({ editing, rev: h.rev, commit, typing: () => setTyping(true) }), [editing, h.rev, commit]);

  /** A field still being typed in is taken over first, so undo and save see it. */
  const flush = () => {
    const el = document.activeElement as HTMLElement | null;
    if (el?.isContentEditable) el.blur();
  };

  const undo = () => { flush(); dispatch({ type: "undo" }); };
  const redo = () => { flush(); dispatch({ type: "redo" }); };

  const save = async () => {
    flush();
    setSaving(true);
    setSaveError(null);
    // The blur above lands in the next render, so the save waits one tick for it.
    await new Promise((r) => window.setTimeout(r, 0));
    try {
      const res = await api.savePage(uuid, pageRef.current);
      setSaved(res.page);
      dispatch({ type: "replace", page: res.page });
    } catch {
      setSaveError(t("saveFailed"));
    } finally {
      setSaving(false);
    }
  };
  const pageRef = useRef(h.page);
  pageRef.current = h.page;

  const onSection = (i: number, action: "up" | "down" | "hide" | "del") => {
    flush();
    const other = action === "up" ? i - 1 : action === "down" ? i + 1 : -1;
    const moveId = other >= 0 ? h.page.sections[i]?.id : null;
    dispatch({
      type: "change",
      fn: (p) => {
        const S = p.sections;
        if (action === "up" && i > 0) [S[i - 1], S[i]] = [S[i], S[i - 1]];
        if (action === "down" && i < S.length - 1) [S[i + 1], S[i]] = [S[i], S[i + 1]];
        if (action === "hide") S[i].hidden = !S[i].hidden;
        if (action === "del") S.splice(i, 1);
      },
    });
    // The moved section stays in view, the reader follows it instead of losing it.
    if (moveId) window.setTimeout(() => document.getElementById(moveId)?.scrollIntoView({ block: "center" }), 0);
  };

  // Ctrl+Z and Ctrl+Shift+Z while editing, also from inside a text.
  useEffect(() => {
    if (!editing) return;
    const onKey = (e: KeyboardEvent) => {
      if (!(e.ctrlKey || e.metaKey) || e.key.toLowerCase() !== "z") return;
      e.preventDefault();
      if (e.shiftKey) redo();
      else undo();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  });

  // Leaving with unsaved changes asks first, the browser shows its own question.
  useEffect(() => {
    if (!dirty) return;
    const warn = (e: BeforeUnloadEvent) => { e.preventDefault(); e.returnValue = t("leave"); };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty, t]);

  const toggleShare = async (on: boolean) => {
    setShareBusy(true);
    try {
      const res = await api.setShare(uuid, on);
      setShare({ shared: res.shared, code: res.code });
    } finally {
      setShareBusy(false);
    }
  };

  return (
    <EditCtx.Provider value={ctx}>
      <PageBar back="/tools/pages" backLabel={t("back")}>
        <Tabs<"edit" | "view">
          variant="pill"
          className="mr-1.5"
          active={editing ? "edit" : "view"}
          onChange={(k) => { flush(); setEditing(k === "edit"); }}
          items={[{ key: "edit", label: t("modeEdit") }, { key: "view", label: t("modeView") }]}
        />
        <button
          type="button"
          onClick={() => setShareOpen(true)}
          className="relative w-7 h-7 flex items-center justify-center rounded-full btn-icon flex-shrink-0"
          style={{ backgroundColor: "var(--surface-dim)" }}
          title={share.shared ? t("shareTitleOn") : t("shareTitleOff")}
          aria-label={share.shared ? t("shareTitleOn") : t("shareTitleOff")}
        >
          <ShareNetwork size={17} weight="regular" />
          {share.shared && (
            <span className="absolute -top-0.5 -right-0.5 w-2.5 h-2.5 rounded-full" style={{ backgroundColor: "var(--success)", border: "2px solid var(--background)" }} />
          )}
        </button>
      </PageBar>
      {editing && (
        <div className="kis-page-hint px-4 py-1.5 text-xs" style={{ background: "rgba(var(--kb-rgb),.05)", borderBottom: "2px solid rgba(var(--kb-rgb),.15)", color: "var(--kb-dark)" }}>
          {t("editHint")}
        </div>
      )}
      <PageView
        page={h.page}
        limits={limits}
        imageBase={api.imageBase({ uuid })}
        edit={{
          canUndo: h.past.length > 0 || typing,
          canRedo: h.future.length > 0,
          dirty,
          saving,
          error: saveError,
          onUndo: undo,
          onRedo: redo,
          onReset: () => { flush(); setTyping(false); dispatch({ type: "change", fn: (p) => Object.assign(p, clone(saved)) }); },
          onSave: save,
          onSection,
        }}
      />
      {editing && <DeleteOnHover onDelete={(path, section) => {
        flush();
        dispatch({
          type: "change",
          fn: (p) => {
            if (section != null) p.sections.splice(section, 1);
            else {
              deleteAt(p, path);
              dropEmptyBlocks(p);
            }
          },
        });
      }} />}
      <ScrollTopButton />
      <ShareModal
        open={shareOpen}
        onClose={() => setShareOpen(false)}
        shared={share.shared}
        link={share.code ? api.shareUrl(share.code) : null}
        busy={shareBusy}
        onToggle={toggleShare}
      />
    </EditCtx.Provider>
  );
}

/**
 * The round bin that follows the pointer while editing. It sits on the innermost element
 * under the pointer: an item, a text, a block or a whole section, which turns red on hover.
 */
function DeleteOnHover({ onDelete }: { onDelete: (path: string, section: number | null) => void }) {
  const t = useTranslations("tools.pages");
  const btn = useRef<HTMLButtonElement>(null);
  const target = useRef<HTMLElement | null>(null);

  useEffect(() => {
    const b = btn.current!;
    const hide = () => {
      b.classList.remove("on");
      target.current?.classList.remove("ed-target");
      target.current = null;
    };
    const move = (e: MouseEvent) => {
      const el = e.target as HTMLElement;
      if (el.closest(".kis-page-del")) return;
      if (!el.closest(".kis-page") || el.closest(".ed-tools,.ed-actions,.ed-save,.pfoot")) return hide();
      const hit = el.closest<HTMLElement>("[data-d],[data-p]:not([data-keep]),.kis-page section");
      if (!hit) return hide();
      if (hit === target.current) return;
      target.current?.classList.remove("ed-target");
      target.current = hit;
      const r = hit.getBoundingClientRect();
      const isSection = hit.tagName === "SECTION";
      const top = isSection ? parseFloat(getComputedStyle(hit, "::before").top) || 0 : 0;
      b.style.top = `${r.top + window.scrollY + top - 12}px`;
      b.style.left = `${Math.min(r.right + window.scrollX + (isSection ? 16 : 0) - 16, document.documentElement.clientWidth - 32)}px`;
      b.classList.add("on");
    };
    document.addEventListener("mousemove", move);
    return () => { document.removeEventListener("mousemove", move); hide(); };
  }, []);

  // On the body, so its position is the page's and no parent can shift it.
  return createPortal(
    <button
      ref={btn}
      type="button"
      className="kis-page-del"
      aria-label={t("removeElement")}
      title={t("remove")}
      onMouseEnter={() => target.current?.classList.add("ed-target")}
      onMouseLeave={() => target.current?.classList.remove("ed-target")}
      onClick={() => {
        const el = target.current;
        if (!el) return;
        el.classList.remove("ed-target");
        btn.current?.classList.remove("on");
        target.current = null;
        if (el.tagName === "SECTION") onDelete("", Number(el.dataset.i));
        else onDelete(el.dataset.d ?? el.dataset.p ?? "", null);
      }}
    >
      <Trash size={15} weight="bold" />
    </button>,
    document.body,
  );
}

"use client";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { useGlossaries, MAX_ENTRIES_PER_GLOSSARY } from "@/hooks/useGlossaries";

const MAX_SELECTED = 3;

interface Props {
  values: string[];   // Array of up to 3 glossary IDs
  onChange: (ids: string[]) => void;
}

export default function GlossarySelector({ values, onChange }: Props) {
  const t = useTranslations("glossarySelector");
  const { glossaries } = useGlossaries();
  const [open, setOpen] = useState(false);
  const [dragIndex, setDragIndex] = useState<number | null>(null);
  const [dragOverIndex, setDragOverIndex] = useState<number | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open]);

  if (glossaries.length === 0) {
    return (
      <div className="mb-4">
        <p className="text-sm text-muted-soft">
          {t("noneCreated")}{" "}
          <Link href="/tools/glossary" className="text-kb hover:underline">
            {t("manageLink")}
          </Link>
        </p>
      </div>
    );
  }

  const selectedIds = values.filter(Boolean);
  const atMax = selectedIds.length >= MAX_SELECTED;

  const toggleGlossary = (id: string) => {
    if (selectedIds.includes(id)) {
      onChange(selectedIds.filter(sid => sid !== id));
    } else if (!atMax) {
      onChange([...selectedIds, id]);
    }
  };

  const removeTag = (id: string) => {
    onChange(selectedIds.filter(sid => sid !== id));
  };

  const handleDragStart = (index: number) => setDragIndex(index);

  const handleDragOver = (e: React.DragEvent, index: number) => {
    e.preventDefault();
    setDragOverIndex(index);
  };

  const handleDrop = (index: number) => {
    if (dragIndex !== null && dragIndex !== index) {
      const reordered = [...selectedIds];
      const [moved] = reordered.splice(dragIndex, 1);
      reordered.splice(index, 0, moved);
      onChange(reordered);
    }
    setDragIndex(null);
    setDragOverIndex(null);
  };

  const handleDragEnd = () => {
    setDragIndex(null);
    setDragOverIndex(null);
  };

  const buttonLabel =
    selectedIds.length === 0
      ? t("noneSelected")
      : t("selected", { count: selectedIds.length });

  return (
    <div className="mb-4 mt-6">
      {/* Dropdown trigger */}
      <div ref={containerRef} className="relative">
        <button
          type="button"
          onClick={() => setOpen(prev => !prev)}
          className="group w-full flex items-center justify-between rounded-md border-2 border-border bg-background px-3 py-2 text-sm shadow-sm transition-colors hover:border-kb focus:border-kb focus:ring-1 focus:ring-kb focus:outline-none"
        >
          <span className={selectedIds.length === 0 ? "text-muted-soft" : "text-foreground-soft"}>
            {buttonLabel}
          </span>
          <svg
            className={`w-4 h-4 transition-all flex-shrink-0 text-muted group-hover:text-kb group-focus:text-kb ${open ? "rotate-180 text-kb" : ""}`}
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            aria-hidden="true"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </button>

        {open && (
          <ul
            className="absolute z-10 mt-1 w-full rounded-md max-h-60 overflow-auto py-1"
            role="listbox"
            aria-multiselectable="true"
            style={{
              backgroundColor: "var(--background)",
              border: "1px solid var(--border)",
              boxShadow: "0 8px 24px rgba(0,40,60,0.12)",
            }}
          >
            {glossaries.map(g => {
              const isSelected = selectedIds.includes(g.id);
              const isDisabled = atMax && !isSelected;
              return (
                <li key={g.id}>
                  <label
                    className={`flex items-center gap-3 px-3 py-2 text-sm select-none ${
                      isDisabled ? "opacity-40 cursor-not-allowed" : "cursor-pointer hover:bg-surface"
                    }`}
                  >
                    <input
                      type="checkbox"
                      checked={isSelected}
                      disabled={isDisabled}
                      onChange={() => toggleGlossary(g.id)}
                      className="h-4 w-4 rounded border-border text-kb focus:ring-kb flex-shrink-0"
                    />
                    <span className="flex-1 text-foreground-soft">{g.name}</span>
                    <span className="text-muted-soft text-xs">
                      {t("entries", { n: Object.keys(g.entries).length })}
                    </span>
                  </label>
                </li>
              );
            })}
          </ul>
        )}
      </div>

      {/* Selected tags */}
      {selectedIds.length > 0 && (
        <div className="flex flex-wrap gap-2 mt-2">
          {selectedIds.map((id, index) => {
            const g = glossaries.find(gl => gl.id === id);
            if (!g) return null;
            const isDraggingThis = dragIndex === index;
            const isDragTarget = dragOverIndex === index && dragIndex !== index;
            return (
              <div
                key={id}
                draggable
                onDragStart={() => handleDragStart(index)}
                onDragOver={(e) => handleDragOver(e, index)}
                onDrop={() => handleDrop(index)}
                onDragEnd={handleDragEnd}
                className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium cursor-grab transition-all ${
                  isDraggingThis
                    ? "opacity-40"
                    : isDragTarget
                      ? "border-kb bg-kb/10 text-kb"
                      : "border-border bg-surface text-foreground-soft"
                }`}
              >
                <span className="text-muted-soft text-[10px]">{index + 1}</span>
                {g.name}
                <button
                  type="button"
                  onClick={() => removeTag(id)}
                  aria-label={t("removeAria", { name: g.name })}
                  className="w-5 h-5 flex items-center justify-center rounded-full text-muted-soft hover:text-kb hover:bg-surface-dim transition-colors"
                >
                  <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>
            );
          })}
        </div>
      )}

      {/* Info text */}
      <p className="mt-2 text-xs text-muted-soft">
        {t("infoOrder")}
        {" · "}{t("infoMax", { n: MAX_SELECTED })}
      </p>
    </div>
  );
}

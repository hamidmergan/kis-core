"use client";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { useGlossaries, MAX_ENTRIES_PER_GLOSSARY } from "@/hooks/useGlossaries";

const MAX_SELECTED = 3;

interface Props {
  values: string[];   // Array of up to 3 glossary IDs
  onChange: (ids: string[]) => void;
}

export default function GlossarySelector({ values, onChange }: Props) {
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
        <p className="text-sm text-gray-400">
          Noch kein Glossar erstellt →{" "}
          <Link href="/tools/glossary" className="text-primary hover:underline">
            Glossare verwalten
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
      ? "Kein Glossar gewählt"
      : selectedIds.length === 1
        ? "1 Glossar gewählt"
        : `${selectedIds.length} Glossare gewählt`;

  return (
    <div className="mb-4 mt-6">
      {/* Dropdown trigger */}
      <div ref={containerRef} className="relative">
        <button
          type="button"
          onClick={() => setOpen(prev => !prev)}
          className="w-full flex items-center justify-between rounded-md border border-gray-300 bg-white px-3 py-2 text-sm shadow-sm hover:bg-gray-100 focus:border-primary focus:ring-1 focus:ring-primary focus:outline-none"
        >
          <span className={selectedIds.length === 0 ? "text-gray-400" : "text-gray-700"}>
            {buttonLabel}
          </span>
          <svg
            className={`w-4 h-4 text-gray-400 transition-transform flex-shrink-0 ${open ? "rotate-180" : ""}`}
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
            className="absolute z-10 mt-1 w-full rounded-md border border-gray-200 bg-white shadow-lg max-h-60 overflow-auto py-1"
            role="listbox"
            aria-multiselectable="true"
          >
            {glossaries.map(g => {
              const isSelected = selectedIds.includes(g.id);
              const isDisabled = atMax && !isSelected;
              return (
                <li key={g.id}>
                  <label
                    className={`flex items-center gap-3 px-3 py-2 text-sm select-none ${
                      isDisabled ? "opacity-40 cursor-not-allowed" : "cursor-pointer hover:bg-gray-100"
                    }`}
                  >
                    <input
                      type="checkbox"
                      checked={isSelected}
                      disabled={isDisabled}
                      onChange={() => toggleGlossary(g.id)}
                      className="h-4 w-4 rounded border-gray-300 text-primary focus:ring-primary flex-shrink-0"
                    />
                    <span className="flex-1 text-gray-700">{g.name}</span>
                    <span className="text-gray-400 text-xs">
                      {Object.keys(g.entries).length} Einträge
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
                      ? "border-primary bg-primary/10 text-primary"
                      : "border-gray-300 bg-gray-100 text-gray-700"
                }`}
              >
                <span className="text-gray-400 text-[10px]">{index + 1}</span>
                {g.name}
                <button
                  type="button"
                  onClick={() => removeTag(id)}
                  aria-label={`${g.name} entfernen`}
                  className="w-5 h-5 flex items-center justify-center rounded-full text-gray-400 hover:text-primary hover:bg-gray-200 transition-colors"
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
      <p className="mt-2 text-xs text-gray-400">
        Bei gleichen Begriffen hat das oben stehende Glossar Vorrang
        {" · "}Max. {MAX_SELECTED} gleichzeitig wählbar
      </p>
    </div>
  );
}

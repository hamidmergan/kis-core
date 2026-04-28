"use client";

import { useState } from "react";

interface EditModuleModalProps {
  currentTitle: string;
  currentDescription: string;
  onClose: () => void;
  onSubmit: (newTitle: string, newDescription: string) => Promise<boolean>;
}

export default function EditModuleModal({
  currentTitle,
  currentDescription,
  onClose,
  onSubmit,
}: EditModuleModalProps) {
  const [title, setTitle] = useState(currentTitle);
  const [description, setDescription] = useState(currentDescription);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSave() {
    const trimmedTitle = title.trim();
    const trimmedDesc = description.trim();
    if (!trimmedTitle) {
      setError("Titel darf nicht leer sein");
      return;
    }
    if (trimmedTitle === currentTitle && trimmedDesc === currentDescription) {
      onClose();
      return;
    }
    setSaving(true);
    setError(null);
    const ok = await onSubmit(trimmedTitle, trimmedDesc);
    setSaving(false);
    if (ok) onClose();
    else setError("Speichern fehlgeschlagen");
  }

  return (
    <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4">
      <div className="bg-white shadow-xl rounded-xl w-full max-h-[90vh] sm:max-w-xl lg:max-w-3xl p-6 flex flex-col">
        <h3 className="text-base font-semibold mb-4">Workspace bearbeiten</h3>
        <div className="mb-4">
          <label className="block text-sm font-medium mb-1" style={{ color: "var(--text)" }}>
            Titel <span style={{ color: "#E11D48" }}>*</span>
          </label>
          <input
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value.slice(0, 50))}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !saving) handleSave();
            }}
            maxLength={50}
            autoFocus
            className="w-full px-3 py-2 text-sm border rounded-lg focus:outline-none focus:ring-2"
            style={{ borderColor: "var(--border)" }}
          />
          <p className="text-xs text-gray-400 text-right mt-1">{title.length}/50</p>
        </div>
        <div className="flex flex-col flex-1 min-h-0">
          <label className="block text-sm font-medium mb-1" style={{ color: "var(--text)" }}>
            Beschreibung
          </label>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value.slice(0, 300))}
            maxLength={300}
            rows={8}
            className="w-full rounded-lg border px-3 py-2 text-sm focus:outline-none resize-none flex-1 sm:min-h-[180px] lg:min-h-[260px]"
            style={{ backgroundColor: "var(--bg)", borderColor: "var(--border)", color: "var(--text)" }}
            placeholder="z. B. Sommersemester 2026, Grundlagen der Programmierung"
          />
          <p className="text-xs text-gray-400 text-right mt-1">{description.length}/300</p>
        </div>
        {error && <p className="text-xs text-red-600 mt-2">{error}</p>}
        <div className="flex gap-3 justify-end mt-5">
          <button
            onClick={onClose}
            disabled={saving}
            className="px-4 py-2 text-sm text-gray-700 border border-gray-300 rounded-lg hover:bg-gray-100 disabled:opacity-50"
          >
            Abbrechen
          </button>
          <button
            onClick={handleSave}
            disabled={saving}
            className="px-4 py-2 text-sm text-white bg-primary rounded-lg disabled:opacity-50"
          >
            {saving ? "..." : "Speichern"}
          </button>
        </div>
      </div>
    </div>
  );
}

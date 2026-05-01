"use client";

import { useState } from "react";
import { Book } from "@phosphor-icons/react";
import { EmptyState } from "@/components/ui/EmptyState";

export interface GlossaryEntry {
  source: string;
  target: string;
}

interface GlossaryPanelProps {
  entries: GlossaryEntry[];
  onChange: (entries: GlossaryEntry[]) => void;
}

export default function GlossaryPanel({ entries, onChange }: GlossaryPanelProps) {
  const [error, setError] = useState<string | null>(null);
  const [newSource, setNewSource] = useState("");
  const [newTarget, setNewTarget] = useState("");

  const handleAddEntry = () => {
    if (!newSource.trim() || !newTarget.trim()) return;
    if (entries.some((e) => e.source.toLowerCase() === newSource.trim().toLowerCase())) {
      setError(`"${newSource.trim()}" existiert bereits im Glossar`);
      return;
    }
    onChange([...entries, { source: newSource.trim(), target: newTarget.trim() }]);
    setNewSource("");
    setNewTarget("");
    setError(null);
  };

  const handleRemoveEntry = (index: number) => {
    onChange(entries.filter((_, i) => i !== index));
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") {
      e.preventDefault();
      handleAddEntry();
    }
  };

  return (
    <div>
      <div className="mb-6">
        <h2 className="text-lg font-semibold mb-1">Glossar</h2>
        <p className="text-sm text-muted">
          Begriffe, die bei der Übersetzung konsistent verwendet werden sollen.
          Einträge gelten nur solange dieser Tab geöffnet ist.
        </p>
      </div>

      {/* Add new entry */}
      <div className="bg-background rounded-lg border border-border-soft p-4 mb-6">
        <div className="flex gap-3 items-end">
          <div className="flex-1">
            <label htmlFor="glossary-source" className="block text-xs font-medium text-foreground-soft mb-1">
              Deutsch (Quelle)
            </label>
            <input
              id="glossary-source"
              type="text"
              value={newSource}
              onChange={(e) => setNewSource(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="z.B. Technische Hochschule"
              className="w-full px-3 py-2 border border-border rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-kb focus:border-transparent"
            />
          </div>
          <div className="flex-1">
            <label htmlFor="glossary-target" className="block text-xs font-medium text-foreground-soft mb-1">
              Englisch (Ziel)
            </label>
            <input
              id="glossary-target"
              type="text"
              value={newTarget}
              onChange={(e) => setNewTarget(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="z.B. University of Applied Sciences"
              className="w-full px-3 py-2 border border-border rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-kb focus:border-transparent"
            />
          </div>
          <button
            onClick={handleAddEntry}
            disabled={!newSource.trim() || !newTarget.trim()}
            className="px-4 py-2 btn-primary text-sm rounded-md disabled:opacity-50 disabled:cursor-not-allowed focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-kb transition-colors whitespace-nowrap"
          >
            Hinzufügen
          </button>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="mb-4 p-3 bg-error-bg border border-error-border rounded-lg text-sm text-error-strong" role="alert">
          {error}
        </div>
      )}

      {/* Entries table */}
      {entries.length === 0 ? (
        <EmptyState
          size="lg"
          icon={<Book size={32} weight="bold" />}
          text="Noch keine Glossar-Einträge vorhanden."
        />
      ) : (
        <div className="bg-background rounded-lg border border-border-soft overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="bg-surface border-b border-border-soft">
                <th className="text-left text-xs font-medium text-muted uppercase tracking-wider px-4 py-3">
                  Deutsch
                </th>
                <th className="text-left text-xs font-medium text-muted uppercase tracking-wider px-4 py-3">
                  Englisch
                </th>
                <th className="w-16 px-4 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-border-soft">
              {entries.map((entry, index) => (
                <tr key={`${entry.source}-${index}`} className="hover:bg-surface transition-colors">
                  <td className="px-4 py-3 text-sm text-foreground">{entry.source}</td>
                  <td className="px-4 py-3 text-sm text-foreground-soft">{entry.target}</td>
                  <td className="px-4 py-3 text-right">
                    <button
                      onClick={() => handleRemoveEntry(index)}
                      aria-label={`${entry.source} entfernen`}
                      className="w-9 h-9 sm:w-7 sm:h-7 flex items-center justify-center rounded-full text-muted-soft hover:text-kb hover:bg-surface transition-colors"
                    >
                      <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                      </svg>
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="px-4 py-3 bg-surface border-t border-border-soft text-xs text-muted">
            {entries.length} {entries.length === 1 ? "Eintrag" : "Einträge"}
          </div>
        </div>
      )}
    </div>
  );
}

"use client";

import { useState } from "react";

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
        <h2 className="text-lg font-semibold text-gray-900 mb-1">Glossar</h2>
        <p className="text-sm text-gray-500">
          Begriffe, die bei der Übersetzung konsistent verwendet werden sollen.
          Einträge gelten nur solange dieser Tab geöffnet ist.
        </p>
      </div>

      {/* Add new entry */}
      <div className="bg-white rounded-lg border border-gray-200 p-4 mb-6">
        <div className="flex gap-3 items-end">
          <div className="flex-1">
            <label htmlFor="glossary-source" className="block text-xs font-medium text-gray-600 mb-1">
              Deutsch (Quelle)
            </label>
            <input
              id="glossary-source"
              type="text"
              value={newSource}
              onChange={(e) => setNewSource(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="z.B. Technische Hochschule"
              className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-[#0066cc] focus:border-transparent"
            />
          </div>
          <div className="flex-1">
            <label htmlFor="glossary-target" className="block text-xs font-medium text-gray-600 mb-1">
              Englisch (Ziel)
            </label>
            <input
              id="glossary-target"
              type="text"
              value={newTarget}
              onChange={(e) => setNewTarget(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="z.B. University of Applied Sciences"
              className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-[#0066cc] focus:border-transparent"
            />
          </div>
          <button
            onClick={handleAddEntry}
            disabled={!newSource.trim() || !newTarget.trim()}
            className="px-4 py-2 bg-[#0066cc] text-white text-sm rounded-md hover:bg-[#0055aa] disabled:opacity-50 disabled:cursor-not-allowed focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#0066cc] transition-colors whitespace-nowrap"
          >
            Hinzufügen
          </button>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700" role="alert">
          {error}
        </div>
      )}

      {/* Entries table */}
      {entries.length === 0 ? (
        <div className="text-center py-12 text-sm text-gray-400">
          Noch keine Glossar-Einträge vorhanden.
        </div>
      ) : (
        <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="bg-gray-50 border-b border-gray-200">
                <th className="text-left text-xs font-medium text-gray-500 uppercase tracking-wider px-4 py-3">
                  Deutsch
                </th>
                <th className="text-left text-xs font-medium text-gray-500 uppercase tracking-wider px-4 py-3">
                  Englisch
                </th>
                <th className="w-16 px-4 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {entries.map((entry, index) => (
                <tr key={`${entry.source}-${index}`} className="hover:bg-gray-50 transition-colors">
                  <td className="px-4 py-3 text-sm text-gray-900">{entry.source}</td>
                  <td className="px-4 py-3 text-sm text-gray-600">{entry.target}</td>
                  <td className="px-4 py-3 text-right">
                    <button
                      onClick={() => handleRemoveEntry(index)}
                      aria-label={`${entry.source} entfernen`}
                      className="text-gray-400 hover:text-red-500 transition-colors"
                    >
                      <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                      </svg>
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="px-4 py-3 bg-gray-50 border-t border-gray-200 text-xs text-gray-500">
            {entries.length} {entries.length === 1 ? "Eintrag" : "Einträge"}
          </div>
        </div>
      )}
    </div>
  );
}

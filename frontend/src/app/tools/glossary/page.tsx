"use client";

import { useRef, useState } from "react";
import { BookOpen, PencilSimple, Trash, DownloadSimple } from "@phosphor-icons/react";
import Header from "@/components/layout/Header";
import ProtectedRoute from "@/components/auth/ProtectedRoute";
import { useGlossaries, MAX_GLOSSARIES, MAX_ENTRIES_PER_GLOSSARY } from "@/hooks/useGlossaries";
import BackLink from "@/components/ui/BackLink";

export default function GlossaryPage() {
  const { glossaries, createGlossary, updateGlossary, deleteGlossary } = useGlossaries();

  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [newName, setNewName] = useState("");
  const [creatingNew, setCreatingNew] = useState(false);
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState("");
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);
  const [newEntryDe, setNewEntryDe] = useState("");
  const [newEntryEn, setNewEntryEn] = useState("");
  const [entryError, setEntryError] = useState("");
  const [importError, setImportError] = useState("");
  const importRef = useRef<HTMLInputElement>(null);

  const selectedGlossary = glossaries.find(g => g.id === selectedId) ?? null;

  const handleCreate = () => {
    if (!newName.trim()) return;
    const id = createGlossary(newName.trim());
    setSelectedId(id);
    setNewName("");
    setCreatingNew(false);
  };

  const handleStartRename = (id: string, currentName: string) => {
    setRenamingId(id);
    setRenameValue(currentName);
  };

  const handleRename = (id: string) => {
    if (!renameValue.trim()) return;
    updateGlossary(id, { name: renameValue.trim() });
    setRenamingId(null);
  };

  const handleDeleteConfirmed = () => {
    if (!confirmDeleteId) return;
    deleteGlossary(confirmDeleteId);
    if (selectedId === confirmDeleteId) setSelectedId(null);
    setConfirmDeleteId(null);
  };

  const handleAddEntry = () => {
    if (!newEntryDe.trim() || !newEntryEn.trim()) return;
    if (!selectedGlossary) return;
    const key = newEntryDe.trim();
    if (key in selectedGlossary.entries) {
      setEntryError(`"${key}" existiert bereits`);
      return;
    }
    updateGlossary(selectedGlossary.id, {
      entries: { ...selectedGlossary.entries, [key]: newEntryEn.trim() },
    });
    setNewEntryDe("");
    setNewEntryEn("");
    setEntryError("");
  };

  const handleRemoveEntry = (key: string) => {
    if (!selectedGlossary) return;
    const updated = { ...selectedGlossary.entries };
    delete updated[key];
    updateGlossary(selectedGlossary.id, { entries: updated });
  };

  const handleExport = (id: string) => {
    const g = glossaries.find(g => g.id === id);
    if (!g) return;
    const payload = { name: g.name, entries: g.entries };
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${g.name}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const handleImport = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setImportError("");
    const reader = new FileReader();
    reader.onload = (ev) => {
      try {
        const parsed = JSON.parse(ev.target?.result as string);
        if (typeof parsed !== "object" || Array.isArray(parsed)) {
          setImportError("Ungültiges Format: JSON-Objekt erwartet.");
          return;
        }

        let name: string;
        let rawEntries: Record<string, unknown>;
        if (
          "entries" in parsed &&
          typeof parsed.entries === "object" &&
          !Array.isArray(parsed.entries) &&
          typeof parsed.name === "string"
        ) {
          name = parsed.name;
          rawEntries = parsed.entries;
        } else {
          name = file.name.replace(/\.json$/i, "");
          rawEntries = parsed;
        }

        const entries: Record<string, string> = {};
        for (const [k, v] of Object.entries(rawEntries)) {
          if (typeof k !== "string" || typeof v !== "string") {
            setImportError("Ungültiges Format: Alle Schlüssel und Werte müssen Strings sein.");
            return;
          }
          entries[k] = v;
        }

        const id = createGlossary(name);
        updateGlossary(id, { entries });
        setSelectedId(id);
      } catch {
        setImportError("Datei konnte nicht gelesen werden. Gültiges JSON erwartet.");
      }
    };
    reader.readAsText(file);
    e.target.value = "";
  };

  const formatDate = (iso: string) => {
    try {
      return new Date(iso).toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit", year: "numeric", timeZone: "Europe/Berlin" });
    } catch {
      return "";
    }
  };

  return (
    <ProtectedRoute>
      <Header showLogout />
      <div className="max-w-4xl mx-auto px-4 py-8">
        <BackLink />
        <section>
          <div className="flex items-center justify-between mb-1">
            <h2 className="text-xl font-bold">Glossary</h2>
            <div className="flex gap-2">
              <input
                ref={importRef}
                type="file"
                accept=".json"
                className="hidden"
                onChange={handleImport}
              />
              <button
                onClick={() => { setImportError(""); importRef.current?.click(); }}
                className="px-3 py-1.5 text-sm border border-gray-300 rounded-md text-gray-600 hover:bg-gray-50 transition-colors"
              >
                Importieren
              </button>
              <button
                onClick={() => setCreatingNew(true)}
                disabled={glossaries.length >= MAX_GLOSSARIES}
                title={glossaries.length >= MAX_GLOSSARIES ? `Maximum erreicht (${MAX_GLOSSARIES}/${MAX_GLOSSARIES})` : undefined}
                className="px-3 py-1.5 text-sm bg-primary text-white rounded-md hover:bg-primary-hover disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                {glossaries.length >= MAX_GLOSSARIES
                  ? `Maximum erreicht (${MAX_GLOSSARIES}/${MAX_GLOSSARIES})`
                  : "+ Neues Glossar"}
              </button>
            </div>
          </div>
          {importError && (
            <p className="mt-2 mb-0 text-sm text-red-600">{importError}</p>
          )}
          <p className="text-sm text-gray-500 mb-6 mt-1">
            Erstellen und verwalten Sie Begriffslisten für konsistente Übersetzungen.
          </p>

          {/* Create new glossary */}
          {creatingNew && (
            <div className="mb-4 flex gap-2">
              <input
                type="text"
                autoFocus
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                onKeyDown={(e) => { if (e.key === "Enter") handleCreate(); if (e.key === "Escape") setCreatingNew(false); }}
                placeholder="Name des Glossars"
                className="flex-1 rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-primary focus:ring-1 focus:ring-primary focus:outline-none"
              />
              <button
                onClick={handleCreate}
                disabled={!newName.trim()}
                className="px-4 py-2 text-sm bg-primary text-white rounded-md hover:bg-primary-hover disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                Erstellen
              </button>
              <button
                onClick={() => { setCreatingNew(false); setNewName(""); }}
                className="px-3 py-2 text-sm border border-gray-300 rounded-md text-gray-600 hover:bg-gray-50 transition-colors"
              >
                Abbrechen
              </button>
            </div>
          )}

          {/* Delete confirmation dialog */}
          {confirmDeleteId && (
            <div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-lg flex items-center justify-between gap-4">
              <p className="text-sm text-red-700">
                Glossar &ldquo;{glossaries.find(g => g.id === confirmDeleteId)?.name}&rdquo; wirklich löschen?
              </p>
              <div className="flex gap-2 shrink-0">
                <button
                  onClick={handleDeleteConfirmed}
                  className="px-3 py-1.5 text-sm bg-red-600 text-white rounded-md hover:bg-red-700 transition-colors"
                >
                  Löschen
                </button>
                <button
                  onClick={() => setConfirmDeleteId(null)}
                  className="px-3 py-1.5 text-sm border border-gray-300 rounded-md text-gray-600 hover:bg-gray-50 transition-colors"
                >
                  Abbrechen
                </button>
              </div>
            </div>
          )}

          {/* Glossary list with inline accordion */}
          {glossaries.length === 0 ? (
            <div className="text-center py-12 text-sm text-gray-400 border border-dashed border-gray-200 rounded-lg">
              Noch keine Glossare vorhanden. Erstellen Sie Ihr erstes Glossar.
            </div>
          ) : (
            <div className="border border-gray-200 rounded-lg overflow-hidden">
              {glossaries.map((g, i) => (
                <div key={g.id}>
                  {/* Glossary row */}
                  <div
                    className={`flex items-center gap-3 px-4 py-3 cursor-pointer transition-colors ${
                      selectedId === g.id ? "bg-[#e8f0fb]" : "bg-white hover:bg-gray-50"
                    } ${i > 0 ? "border-t border-gray-100" : ""}`}
                    onClick={() => setSelectedId(g.id === selectedId ? null : g.id)}
                  >
                    <BookOpen size={16} weight="regular" className="text-gray-400 shrink-0" />
                    {renamingId === g.id ? (
                      <input
                        type="text"
                        autoFocus
                        value={renameValue}
                        onChange={(e) => setRenameValue(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === "Enter") handleRename(g.id);
                          if (e.key === "Escape") setRenamingId(null);
                        }}
                        onBlur={() => handleRename(g.id)}
                        onClick={(e) => e.stopPropagation()}
                        className="flex-1 rounded border border-gray-300 px-2 py-0.5 text-sm focus:border-primary focus:outline-none"
                      />
                    ) : (
                      <div className="flex-1 min-w-0">
                        <span className="text-sm font-medium text-gray-800">{g.name} </span>
                        <span className="text-sm text-gray-400">
                          ({Object.keys(g.entries).length} Einträge)
                        </span>
                        <span className="ml-2 text-xs text-gray-300">· {formatDate(g.createdAt)}</span>
                      </div>
                    )}
                    <div className="flex gap-1 shrink-0" onClick={(e) => e.stopPropagation()}>
                      <button
                        onClick={() => handleStartRename(g.id, g.name)}
                        className="p-1.5 text-gray-400 hover:text-gray-600 transition-colors"
                        title="Umbenennen"
                      >
                        <PencilSimple size={15} weight="regular" />
                      </button>
                      <button
                        onClick={() => handleExport(g.id)}
                        className="p-1.5 text-gray-400 hover:text-gray-600 transition-colors"
                        title="Als JSON exportieren"
                      >
                        <DownloadSimple size={15} weight="regular" />
                      </button>
                      <button
                        onClick={() => setConfirmDeleteId(g.id)}
                        className="p-1.5 text-gray-400 hover:text-red-500 transition-colors"
                        title="Löschen"
                      >
                        <Trash size={15} weight="regular" />
                      </button>
                    </div>
                  </div>

                  {/* Inline accordion: entries panel */}
                  {selectedId === g.id && (
                    <div className="border-t border-gray-200 bg-gray-50 px-4 py-4">
                      {/* Add entry */}
                      <div className="flex gap-2 mb-3">
                        <input
                          type="text"
                          value={newEntryDe}
                          onChange={(e) => { setNewEntryDe(e.target.value); setEntryError(""); }}
                          onKeyDown={(e) => { if (e.key === "Enter") handleAddEntry(); }}
                          placeholder="Deutsch"
                          className="flex-1 rounded-md border border-gray-300 px-3 py-2 text-sm bg-white focus:border-primary focus:ring-1 focus:ring-primary focus:outline-none"
                        />
                        <input
                          type="text"
                          value={newEntryEn}
                          onChange={(e) => { setNewEntryEn(e.target.value); setEntryError(""); }}
                          onKeyDown={(e) => { if (e.key === "Enter") handleAddEntry(); }}
                          placeholder="Englisch"
                          className="flex-1 rounded-md border border-gray-300 px-3 py-2 text-sm bg-white focus:border-primary focus:ring-1 focus:ring-primary focus:outline-none"
                        />
                        <button
                          onClick={handleAddEntry}
                          disabled={!newEntryDe.trim() || !newEntryEn.trim() || Object.keys(g.entries).length >= MAX_ENTRIES_PER_GLOSSARY}
                          title={Object.keys(g.entries).length >= MAX_ENTRIES_PER_GLOSSARY ? `Maximum erreicht (${MAX_ENTRIES_PER_GLOSSARY}/${MAX_ENTRIES_PER_GLOSSARY})` : undefined}
                          className="px-4 py-2 text-sm bg-primary text-white rounded-md hover:bg-primary-hover disabled:opacity-50 disabled:cursor-not-allowed transition-colors whitespace-nowrap"
                        >
                          {Object.keys(g.entries).length >= MAX_ENTRIES_PER_GLOSSARY
                            ? `Maximum erreicht (${MAX_ENTRIES_PER_GLOSSARY}/${MAX_ENTRIES_PER_GLOSSARY})`
                            : "+ Eintrag"}
                        </button>
                      </div>

                      {entryError && (
                        <p className="mb-2 text-sm text-red-600">{entryError}</p>
                      )}

                      {Object.keys(g.entries).length === 0 ? (
                        <div className="text-center py-6 text-sm text-gray-400 border border-dashed border-gray-200 rounded-lg bg-white">
                          Noch keine Einträge vorhanden.
                        </div>
                      ) : (
                        <div className="border border-gray-200 rounded-lg overflow-hidden">
                          <table className="w-full">
                            <thead>
                              <tr className="bg-white border-b border-gray-200">
                                <th className="text-left text-xs font-medium text-gray-500 uppercase tracking-wider px-4 py-2.5">
                                  Deutsch
                                </th>
                                <th className="text-left text-xs font-medium text-gray-500 uppercase tracking-wider px-4 py-2.5">
                                  Englisch
                                </th>
                                <th className="w-12 px-4 py-2.5" />
                              </tr>
                            </thead>
                            <tbody className="divide-y divide-gray-100">
                              {Object.entries(g.entries).map(([de, en]) => (
                                <tr key={de} className="bg-white hover:bg-gray-50 transition-colors">
                                  <td className="px-4 py-2.5 text-sm text-gray-900">{de}</td>
                                  <td className="px-4 py-2.5 text-sm text-gray-600">{en}</td>
                                  <td className="px-4 py-2.5 text-right">
                                    <button
                                      onClick={() => handleRemoveEntry(de)}
                                      aria-label={`${de} entfernen`}
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
                          <div className="px-4 py-2.5 bg-white border-t border-gray-100 text-xs text-gray-400">
                            {Object.keys(g.entries).length} / {MAX_ENTRIES_PER_GLOSSARY} Einträge
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </section>
      </div>
    </ProtectedRoute>
  );
}

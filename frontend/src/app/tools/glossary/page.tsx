"use client";

import { useRef, useState } from "react";
import { BookOpen, PencilSimple, Trash, DownloadSimple } from "@phosphor-icons/react";
import ProtectedRoute from "@/components/auth/ProtectedRoute";
import { useGlossaries, MAX_GLOSSARIES, MAX_ENTRIES_PER_GLOSSARY } from "@/hooks/useGlossaries";
import BackLink from "@/components/ui/BackLink";
import { EmptyState } from "@/components/ui/EmptyState";

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
      <div className="max-w-4xl mx-auto px-4 py-8">
        <BackLink />
        <section>
          <div className="flex items-center justify-between mb-1">
            <h2 className="text-xl font-bold">Glossar</h2>
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
                className="px-3 py-1.5 text-sm border border-border rounded-md text-foreground-soft hover:bg-surface transition-colors"
              >
                Importieren
              </button>
              <button
                onClick={() => setCreatingNew(true)}
                disabled={glossaries.length >= MAX_GLOSSARIES}
                title={glossaries.length >= MAX_GLOSSARIES ? `Maximum erreicht (${MAX_GLOSSARIES}/${MAX_GLOSSARIES})` : undefined}
                className="px-3 py-1.5 text-sm btn-primary rounded-md  disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                {glossaries.length >= MAX_GLOSSARIES
                  ? `Maximum erreicht (${MAX_GLOSSARIES}/${MAX_GLOSSARIES})`
                  : "+ Neues Glossar"}
              </button>
            </div>
          </div>
          {importError && (
            <p className="mt-2 mb-0 text-sm text-error">{importError}</p>
          )}
          <p className="text-sm text-muted mb-6 mt-1">
            Eigene Begriffslisten anlegen für konsistente Fachbegriffe in Übersetzungen.
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
                placeholder="Name des Glossaries"
                className="flex-1 rounded-md border border-border px-3 py-2 text-sm focus:border-kb focus:ring-1 focus:ring-kb focus:outline-none"
              />
              <button
                onClick={handleCreate}
                disabled={!newName.trim()}
                className="px-4 py-2 text-sm btn-primary rounded-md  disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                Erstellen
              </button>
              <button
                onClick={() => { setCreatingNew(false); setNewName(""); }}
                className="px-3 py-2 text-sm border border-border rounded-md text-foreground-soft hover:bg-surface transition-colors"
              >
                Abbrechen
              </button>
            </div>
          )}

          {/* Delete confirmation dialog */}
          {confirmDeleteId && (
            <div className="mb-4 p-4 bg-error-bg border border-error-border rounded-lg flex items-center justify-between gap-4">
              <p className="text-sm text-error-strong">
                Glossar &ldquo;{glossaries.find(g => g.id === confirmDeleteId)?.name}&rdquo; wirklich löschen?
              </p>
              <div className="flex gap-2 shrink-0">
                <button
                  onClick={handleDeleteConfirmed}
                  className="px-3 py-1.5 text-sm bg-error text-white rounded-md hover:bg-error-strong transition-colors"
                >
                  Löschen
                </button>
                <button
                  onClick={() => setConfirmDeleteId(null)}
                  className="px-3 py-1.5 text-sm border border-border rounded-md text-foreground-soft hover:bg-surface transition-colors"
                >
                  Abbrechen
                </button>
              </div>
            </div>
          )}

          {/* Glossary list with inline accordion */}
          {glossaries.length === 0 ? (
            <div className="border border-dashed border-border-soft rounded-lg">
              <EmptyState
                size="lg"
                icon={<BookOpen size={32} weight="bold" />}
                text="Noch keine Glossare vorhanden. Erstellen Sie Ihr erstes Glossar."
              />
            </div>
          ) : (
            <div className="border border-border-soft rounded-lg overflow-hidden">
              {glossaries.map((g, i) => (
                <div key={g.id}>
                  {/* Glossary row */}
                  <div
                    className={`flex items-center gap-3 px-4 py-3 cursor-pointer transition-colors ${
                      selectedId === g.id ? "bg-[var(--kb20)]" : "bg-white hover:bg-surface"
                    } ${i > 0 ? "border-t border-border-soft" : ""}`}
                    onClick={() => setSelectedId(g.id === selectedId ? null : g.id)}
                  >
                    <BookOpen size={16} weight="regular" className="text-muted-soft shrink-0" />
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
                        className="flex-1 rounded border border-border px-2 py-0.5 text-sm focus:border-kb focus:outline-none"
                      />
                    ) : (
                      <div className="flex-1 min-w-0">
                        <span className="text-sm font-medium text-foreground">{g.name} </span>
                        <span className="text-sm text-muted-soft">
                          ({Object.keys(g.entries).length} Einträge)
                        </span>
                        <span className="ml-2 text-xs text-border">· {formatDate(g.createdAt)}</span>
                      </div>
                    )}
                    <div className="flex gap-1 shrink-0" onClick={(e) => e.stopPropagation()}>
                      <button
                        onClick={() => handleStartRename(g.id, g.name)}
                        className="p-1.5 text-muted-soft hover:text-foreground-soft transition-colors"
                        title="Umbenennen"
                      >
                        <PencilSimple size={15} weight="regular" />
                      </button>
                      <button
                        onClick={() => handleExport(g.id)}
                        className="p-1.5 text-muted-soft hover:text-foreground-soft transition-colors"
                        title="Als JSON exportieren"
                      >
                        <DownloadSimple size={15} weight="regular" />
                      </button>
                      <button
                        onClick={() => setConfirmDeleteId(g.id)}
                        className="p-1.5 text-muted-soft hover:text-error transition-colors"
                        title="Löschen"
                      >
                        <Trash size={15} weight="regular" />
                      </button>
                    </div>
                  </div>

                  {/* Inline accordion: entries panel */}
                  {selectedId === g.id && (
                    <div className="border-t border-border-soft bg-surface px-4 py-4">
                      {/* Add entry */}
                      <div className="flex gap-2 mb-3">
                        <input
                          type="text"
                          value={newEntryDe}
                          onChange={(e) => { setNewEntryDe(e.target.value); setEntryError(""); }}
                          onKeyDown={(e) => { if (e.key === "Enter") handleAddEntry(); }}
                          placeholder="Deutsch"
                          className="flex-1 rounded-md border border-border px-3 py-2 text-sm bg-white focus:border-kb focus:ring-1 focus:ring-kb focus:outline-none"
                        />
                        <input
                          type="text"
                          value={newEntryEn}
                          onChange={(e) => { setNewEntryEn(e.target.value); setEntryError(""); }}
                          onKeyDown={(e) => { if (e.key === "Enter") handleAddEntry(); }}
                          placeholder="Englisch"
                          className="flex-1 rounded-md border border-border px-3 py-2 text-sm bg-white focus:border-kb focus:ring-1 focus:ring-kb focus:outline-none"
                        />
                        <button
                          onClick={handleAddEntry}
                          disabled={!newEntryDe.trim() || !newEntryEn.trim() || Object.keys(g.entries).length >= MAX_ENTRIES_PER_GLOSSARY}
                          title={Object.keys(g.entries).length >= MAX_ENTRIES_PER_GLOSSARY ? `Maximum erreicht (${MAX_ENTRIES_PER_GLOSSARY}/${MAX_ENTRIES_PER_GLOSSARY})` : undefined}
                          className="px-4 py-2 text-sm btn-primary rounded-md  disabled:opacity-50 disabled:cursor-not-allowed transition-colors whitespace-nowrap"
                        >
                          {Object.keys(g.entries).length >= MAX_ENTRIES_PER_GLOSSARY
                            ? `Maximum erreicht (${MAX_ENTRIES_PER_GLOSSARY}/${MAX_ENTRIES_PER_GLOSSARY})`
                            : "+ Eintrag"}
                        </button>
                      </div>

                      {entryError && (
                        <p className="mb-2 text-sm text-error">{entryError}</p>
                      )}

                      {Object.keys(g.entries).length === 0 ? (
                        <div className="border border-dashed border-border-soft rounded-lg bg-white">
                          <EmptyState
                            size="sm"
                            text="Noch keine Einträge vorhanden."
                          />
                        </div>
                      ) : (
                        <div className="border border-border-soft rounded-lg overflow-hidden">
                          <table className="w-full">
                            <thead>
                              <tr className="bg-white border-b border-border-soft">
                                <th className="text-left text-xs font-medium text-muted uppercase tracking-wider px-4 py-2.5">
                                  Deutsch
                                </th>
                                <th className="text-left text-xs font-medium text-muted uppercase tracking-wider px-4 py-2.5">
                                  Englisch
                                </th>
                                <th className="w-12 px-4 py-2.5" />
                              </tr>
                            </thead>
                            <tbody className="divide-y divide-border-soft">
                              {Object.entries(g.entries).map(([de, en]) => (
                                <tr key={de} className="bg-white hover:bg-surface transition-colors">
                                  <td className="px-4 py-2.5 text-sm text-foreground">{de}</td>
                                  <td className="px-4 py-2.5 text-sm text-foreground-soft">{en}</td>
                                  <td className="px-4 py-2.5 text-right">
                                    <button
                                      onClick={() => handleRemoveEntry(de)}
                                      aria-label={`${de} entfernen`}
                                      className="text-muted-soft hover:text-error transition-colors"
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
                          <div className="px-4 py-2.5 bg-white border-t border-border-soft text-xs text-muted-soft">
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

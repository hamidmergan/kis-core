"use client";

import { useRef, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { BookOpen, PencilSimple, Trash, DownloadSimple } from "@phosphor-icons/react";
import ProtectedRoute from "@/components/auth/ProtectedRoute";
import { useGlossaries, MAX_GLOSSARIES, MAX_ENTRIES_PER_GLOSSARY } from "@/hooks/useGlossaries";
import { EmptyState } from "@/components/ui/EmptyState";

export default function GlossaryPage() {
  const t = useTranslations("tools.glossary");
  const tImport = useTranslations("tools.glossary.import_");
  const locale = useLocale();
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

  const handleCreate = async () => {
    if (!newName.trim()) return;
    const id = await createGlossary(newName.trim());
    setSelectedId(id);
    setNewName("");
    setCreatingNew(false);
  };

  const handleStartRename = (id: string, currentName: string) => {
    setRenamingId(id);
    setRenameValue(currentName);
  };

  const handleRename = async (id: string) => {
    if (!renameValue.trim()) return;
    await updateGlossary(id, { name: renameValue.trim() });
    setRenamingId(null);
  };

  const handleDeleteConfirmed = async () => {
    if (!confirmDeleteId) return;
    const deletedId = confirmDeleteId;
    await deleteGlossary(deletedId);
    if (selectedId === deletedId) setSelectedId(null);
    setConfirmDeleteId(null);
  };

  const handleAddEntry = async () => {
    if (!newEntryDe.trim() || !newEntryEn.trim()) return;
    if (!selectedGlossary) return;
    const key = newEntryDe.trim();
    if (key in selectedGlossary.entries) {
      setEntryError(t("duplicateEntry", { key }));
      return;
    }
    await updateGlossary(selectedGlossary.id, {
      entries: { ...selectedGlossary.entries, [key]: newEntryEn.trim() },
    });
    setNewEntryDe("");
    setNewEntryEn("");
    setEntryError("");
  };

  const handleRemoveEntry = async (key: string) => {
    if (!selectedGlossary) return;
    const updated = { ...selectedGlossary.entries };
    delete updated[key];
    await updateGlossary(selectedGlossary.id, { entries: updated });
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
    reader.onload = async (ev) => {
      try {
        const parsed = JSON.parse(ev.target?.result as string);
        if (typeof parsed !== "object" || Array.isArray(parsed)) {
          setImportError(tImport("invalidJsonObject"));
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
            setImportError(tImport("invalidStrings"));
            return;
          }
          entries[k] = v;
        }

        const id = await createGlossary(name, entries);
        setSelectedId(id);
      } catch {
        setImportError(tImport("readFailed"));
      }
    };
    reader.readAsText(file);
    e.target.value = "";
  };

  const formatDate = (iso: string) => {
    try {
      const tag = locale === "en" ? "en-US" : "de-DE";
      return new Date(iso).toLocaleDateString(tag, { day: "2-digit", month: "2-digit", year: "numeric", timeZone: "Europe/Berlin" });
    } catch {
      return "";
    }
  };

  return (
    <ProtectedRoute>
      <div className="max-w-4xl mx-auto px-4 py-8">
        <section>
          <div className="flex items-center justify-between mb-1">
            <h2 className="text-xl font-bold">{t("title")}</h2>
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
                {t("import")}
              </button>
              <button
                onClick={() => setCreatingNew(true)}
                disabled={glossaries.length >= MAX_GLOSSARIES}
                title={glossaries.length >= MAX_GLOSSARIES ? t("maxReached", { current: MAX_GLOSSARIES, max: MAX_GLOSSARIES }) : undefined}
                className="px-3 py-1.5 text-sm btn-primary rounded-md  disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                {glossaries.length >= MAX_GLOSSARIES
                  ? t("maxReached", { current: MAX_GLOSSARIES, max: MAX_GLOSSARIES })
                  : t("newButton")}
              </button>
            </div>
          </div>
          {importError && (
            <p className="mt-2 mb-0 text-sm text-error">{importError}</p>
          )}
          <p className="text-sm text-muted mb-6 mt-1">
            {t("intro")}
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
                placeholder={t("namePlaceholder")}
                className="flex-1 rounded-md border border-border px-3 py-2 text-sm focus:border-kb focus:ring-1 focus:ring-kb focus:outline-none"
              />
              <button
                onClick={handleCreate}
                disabled={!newName.trim()}
                className="px-4 py-2 text-sm btn-primary rounded-md  disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                {t("create")}
              </button>
              <button
                onClick={() => { setCreatingNew(false); setNewName(""); }}
                className="btn-cancel px-3 py-2 text-sm border border-border rounded-md text-foreground-soft transition-colors"
              >
                {t("cancel")}
              </button>
            </div>
          )}

          {/* Delete confirmation dialog */}
          {confirmDeleteId && (
            <div className="mb-4 p-4 bg-error-bg border border-error-border rounded-lg flex items-center justify-between gap-4">
              <p className="text-sm text-error-strong">
                {t("deleteConfirm", { name: glossaries.find(g => g.id === confirmDeleteId)?.name ?? "" })}
              </p>
              <div className="flex gap-2 shrink-0">
                <button
                  onClick={handleDeleteConfirmed}
                  className="px-3 py-1.5 text-sm bg-error text-white rounded-md hover:bg-error-strong transition-colors"
                >
                  {t("delete")}
                </button>
                <button
                  onClick={() => setConfirmDeleteId(null)}
                  className="btn-cancel px-3 py-1.5 text-sm border border-border rounded-md text-foreground-soft transition-colors"
                >
                  {t("cancel")}
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
                text={t("empty")}
              />
            </div>
          ) : (
            <div className="border border-border-soft rounded-lg overflow-hidden">
              {glossaries.map((g, i) => (
                <div key={g.id}>
                  {/* Glossary row */}
                  <div
                    className={`flex items-center gap-3 px-4 py-3 cursor-pointer transition-colors ${
                      selectedId === g.id ? "bg-[var(--kb20)]" : "bg-background hover:bg-surface"
                    } ${i > 0 ? "border-t border-border-soft" : ""}`}
                    onClick={() => setSelectedId(g.id === selectedId ? null : g.id)}
                  >
                    <BookOpen size={16} weight="bold" className="text-muted-soft shrink-0" />
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
                          ({t("entryCount", { n: Object.keys(g.entries).length })})
                        </span>
                        <span className="ml-2 text-xs text-border">· {formatDate(g.createdAt)}</span>
                      </div>
                    )}
                    <div className="flex gap-1 shrink-0" onClick={(e) => e.stopPropagation()}>
                      <button
                        onClick={() => handleStartRename(g.id, g.name)}
                        className="p-1.5 text-muted-soft hover:text-foreground-soft transition-colors"
                        title={t("actionRename")}
                      >
                        <PencilSimple size={15} weight="bold" />
                      </button>
                      <button
                        onClick={() => handleExport(g.id)}
                        className="p-1.5 text-muted-soft hover:text-foreground-soft transition-colors"
                        title={t("actionExport")}
                      >
                        <DownloadSimple size={15} weight="bold" />
                      </button>
                      <button
                        onClick={() => setConfirmDeleteId(g.id)}
                        className="p-1.5 text-muted-soft hover:text-error transition-colors"
                        title={t("actionDelete")}
                      >
                        <Trash size={15} weight="bold" />
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
                          placeholder={t("deTerm")}
                          className="flex-1 rounded-md border border-border px-3 py-2 text-sm bg-background focus:border-kb focus:ring-1 focus:ring-kb focus:outline-none"
                        />
                        <input
                          type="text"
                          value={newEntryEn}
                          onChange={(e) => { setNewEntryEn(e.target.value); setEntryError(""); }}
                          onKeyDown={(e) => { if (e.key === "Enter") handleAddEntry(); }}
                          placeholder={t("enTerm")}
                          className="flex-1 rounded-md border border-border px-3 py-2 text-sm bg-background focus:border-kb focus:ring-1 focus:ring-kb focus:outline-none"
                        />
                        <button
                          onClick={handleAddEntry}
                          disabled={!newEntryDe.trim() || !newEntryEn.trim() || Object.keys(g.entries).length >= MAX_ENTRIES_PER_GLOSSARY}
                          title={Object.keys(g.entries).length >= MAX_ENTRIES_PER_GLOSSARY ? t("maxReached", { current: MAX_ENTRIES_PER_GLOSSARY, max: MAX_ENTRIES_PER_GLOSSARY }) : undefined}
                          className="px-4 py-2 text-sm btn-primary rounded-md  disabled:opacity-50 disabled:cursor-not-allowed transition-colors whitespace-nowrap"
                        >
                          {Object.keys(g.entries).length >= MAX_ENTRIES_PER_GLOSSARY
                            ? t("maxReached", { current: MAX_ENTRIES_PER_GLOSSARY, max: MAX_ENTRIES_PER_GLOSSARY })
                            : t("addEntry")}
                        </button>
                      </div>

                      {entryError && (
                        <p className="mb-2 text-sm text-error">{entryError}</p>
                      )}

                      {Object.keys(g.entries).length === 0 ? (
                        <div className="border border-dashed border-border-soft rounded-lg bg-background">
                          <EmptyState
                            size="sm"
                            text={t("noEntries")}
                          />
                        </div>
                      ) : (
                        <div className="border border-border-soft rounded-lg overflow-hidden">
                          <table className="w-full">
                            <thead>
                              <tr className="bg-background border-b border-border-soft">
                                <th className="text-left text-xs font-medium text-muted uppercase tracking-wider px-4 py-2.5">
                                  {t("deTerm")}
                                </th>
                                <th className="text-left text-xs font-medium text-muted uppercase tracking-wider px-4 py-2.5">
                                  {t("enTerm")}
                                </th>
                                <th className="w-12 px-4 py-2.5" />
                              </tr>
                            </thead>
                            <tbody className="divide-y divide-border-soft">
                              {Object.entries(g.entries).map(([de, en]) => (
                                <tr key={de} className="bg-background hover:bg-surface transition-colors">
                                  <td className="px-4 py-2.5 text-sm text-foreground">{de}</td>
                                  <td className="px-4 py-2.5 text-sm text-foreground-soft">{en}</td>
                                  <td className="px-4 py-2.5 text-right">
                                    <button
                                      onClick={() => handleRemoveEntry(de)}
                                      aria-label={t("removeAria", { term: de })}
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
                          <div className="px-4 py-2.5 bg-background border-t border-border-soft text-xs text-muted-soft">
                            {t("entryFooter", { n: Object.keys(g.entries).length, max: MAX_ENTRIES_PER_GLOSSARY })}
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

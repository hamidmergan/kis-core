"use client";

/** Search a person in the database, then tick which of their workspaces a code enrolls its accounts into. */

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import Checkbox from "@/components/ui/Checkbox";
import Spinner from "@/components/ui/Spinner";

type Owner = {
  user_id: number;
  name: string;
  username: string;
  role: string;
  workspaces: { id: number; title: string }[];
};

/** A workspace already tied to the code, as the code list delivers it. */
type Chosen = { id: number; title: string; owner_id: number | null };

type Props = {
  value: number[];
  onChange: (ids: number[]) => void;
  /** Shown under the field, differs between creating and editing. */
  hint: string;
  /** The workspaces the code already has, so editing shows their titles and owner right away. */
  initial?: Chosen[];
};

const SEARCH_DELAY_MS = 250;

function ownersUrl(params: URLSearchParams): string {
  return `/api/admin/access-codes/workspace-owners?${params.toString()}`;
}

export default function CodeWorkspacesField({ value, onChange, hint, initial = [] }: Props) {
  const t = useTranslations("admin.codeWorkspaces");
  const [query, setQuery] = useState("");
  const [hits, setHits] = useState<Owner[]>([]);
  const [searching, setSearching] = useState(false);
  const [person, setPerson] = useState<Owner | null>(null);
  const [titel, setTitel] = useState<Map<number, string>>(() => new Map(initial.map((w) => [w.id, w.title])));

  // Editing opens on the owner of the first workspace the code already has.
  useEffect(() => {
    const ownerId = initial.find((w) => w.owner_id != null)?.owner_id;
    if (ownerId == null) return;
    fetch(ownersUrl(new URLSearchParams({ user_ids: String(ownerId) })), { credentials: "include" })
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        const gefunden: Owner | undefined = d?.owners?.[0];
        if (gefunden) setPerson(gefunden);
      })
      .catch(() => {});
    // Only the first render decides the preselected person.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const suche = query.trim();
    if (!suche) {
      setHits([]);
      setSearching(false);
      return;
    }
    let aktiv = true;
    setSearching(true);
    const timer = setTimeout(() => {
      fetch(ownersUrl(new URLSearchParams({ q: suche })), { credentials: "include" })
        .then((r) => (r.ok ? r.json() : null))
        .then((d) => { if (aktiv) setHits(d?.owners ?? []); })
        .catch(() => { if (aktiv) setHits([]); })
        .finally(() => { if (aktiv) setSearching(false); });
    }, SEARCH_DELAY_MS);
    return () => {
      aktiv = false;
      clearTimeout(timer);
    };
  }, [query]);

  function waehlen(owner: Owner) {
    setPerson(owner);
    setQuery("");
    setTitel((prev) => {
      const karte = new Map(prev);
      owner.workspaces.forEach((w) => karte.set(w.id, w.title));
      return karte;
    });
  }

  const gewaehlt = new Set(value);
  const gewaehlteTitel = value.map((id) => titel.get(id)).filter((x): x is string => Boolean(x));

  function umschalten(id: number, an: boolean) {
    onChange(an ? [...value, id] : value.filter((x) => x !== id));
  }

  function alleUmschalten(an: boolean) {
    if (!person) return;
    const ids = person.workspaces.map((w) => w.id);
    onChange(an ? [...value.filter((x) => !ids.includes(x)), ...ids] : value.filter((x) => !ids.includes(x)));
  }

  const vonPerson = person ? person.workspaces.filter((w) => gewaehlt.has(w.id)).length : 0;

  return (
    <div className="space-y-1">
      <label className="text-xs uppercase tracking-wide text-muted" htmlFor="code-workspaces-search">
        {t("label")}
      </label>
      <input
        id="code-workspaces-search"
        data-testid="code-workspaces-search"
        type="search"
        autoComplete="off"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder={t("searchPerson")}
        className="w-full text-sm border border-border rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-kb"
      />

      {query.trim() && (
        <div data-testid="code-workspaces-hits" className="max-h-48 overflow-y-auto space-y-1 pt-1">
          {searching ? (
            <Spinner className="flex justify-center py-2" />
          ) : hits.length === 0 ? (
            <p className="text-xs text-muted-soft">{t("noHits")}</p>
          ) : (
            hits.map((o) => (
              <button
                key={o.user_id}
                type="button"
                onClick={() => waehlen(o)}
                className="w-full flex items-center justify-between gap-2 text-left px-3 py-1.5 border-2 border-border hover:border-kb focus:border-kb focus:outline-none rounded-md transition-colors"
              >
                <span className="min-w-0">
                  <span className="block text-sm text-foreground truncate">{o.name}</span>
                  <span className="block text-xs text-muted-soft font-mono truncate">{o.username}</span>
                </span>
                <span className="text-xs text-muted-soft flex-shrink-0">{t("listCount", { n: o.workspaces.length })}</span>
              </button>
            ))
          )}
        </div>
      )}

      {person && (
        <div
          data-testid="code-workspaces-list"
          className="max-h-40 overflow-y-auto overflow-x-hidden border border-border rounded-md px-3 py-2 space-y-1.5"
        >
          <p className="text-xs font-medium text-foreground-soft truncate">{person.name}</p>
          {person.workspaces.length > 1 && (
            <Checkbox
              checked={vonPerson === person.workspaces.length}
              indeterminate={vonPerson > 0 && vonPerson < person.workspaces.length}
              onChange={alleUmschalten}
              label={t("all")}
              labelClassName="text-xs text-muted"
            />
          )}
          {person.workspaces.map((w) => (
            <Checkbox
              key={w.id}
              checked={gewaehlt.has(w.id)}
              onChange={(an) => umschalten(w.id, an)}
              label={w.title}
              className="w-full min-w-0"
              labelClassName="text-xs text-foreground truncate min-w-0"
            />
          ))}
        </div>
      )}

      {gewaehlteTitel.length > 0 && (
        <p className="text-xs text-foreground-soft">
          {t("chosen", { n: gewaehlteTitel.length })}: {gewaehlteTitel.join(", ")}
        </p>
      )}
      <p className="text-xs text-muted-soft">{hint}</p>
    </div>
  );
}

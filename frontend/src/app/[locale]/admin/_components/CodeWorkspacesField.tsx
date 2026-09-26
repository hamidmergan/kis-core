"use client";

/** Pick a person, then tick which of their workspaces a code enrolls its accounts into. */

import { useEffect, useMemo, useState } from "react";
import { useTranslations } from "next-intl";
import Select from "@/components/ui/Select";
import Checkbox from "@/components/ui/Checkbox";

type Owner = {
  user_id: number;
  name: string;
  username: string;
  role: string;
  workspaces: { id: number; title: string }[];
};

type Props = {
  value: number[];
  onChange: (ids: number[]) => void;
  /** Shown under the field, differs between creating and editing. */
  hint: string;
};

export default function CodeWorkspacesField({ value, onChange, hint }: Props) {
  const t = useTranslations("admin.codeWorkspaces");
  const [owners, setOwners] = useState<Owner[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [person, setPerson] = useState("");

  useEffect(() => {
    fetch("/api/admin/access-codes/workspace-owners", { credentials: "include" })
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        const liste: Owner[] = d?.owners ?? [];
        setOwners(liste);
        // Editing opens on the person whose workspace is already chosen.
        const erster = liste.find((o) => o.workspaces.some((w) => value.includes(w.id)));
        if (erster) setPerson(String(erster.user_id));
      })
      .catch(() => {})
      .finally(() => setLoaded(true));
    // Only the first render decides the preselected person.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const personOptions = useMemo(
    () => owners.map((o) => ({ value: String(o.user_id), label: `${o.name} (${o.workspaces.length})` })),
    [owners],
  );

  const aktuell = owners.find((o) => String(o.user_id) === person);
  const gewaehlt = new Set(value);
  const titel = useMemo(() => {
    const karte = new Map<number, string>();
    owners.forEach((o) => o.workspaces.forEach((w) => karte.set(w.id, w.title)));
    return karte;
  }, [owners]);
  const gewaehlteTitel = value.map((id) => titel.get(id)).filter((x): x is string => Boolean(x));

  function umschalten(id: number, an: boolean) {
    onChange(an ? [...value, id] : value.filter((x) => x !== id));
  }

  function alleUmschalten(an: boolean) {
    if (!aktuell) return;
    const ids = aktuell.workspaces.map((w) => w.id);
    onChange(an ? [...value.filter((x) => !ids.includes(x)), ...ids] : value.filter((x) => !ids.includes(x)));
  }

  const vonPerson = aktuell ? aktuell.workspaces.filter((w) => gewaehlt.has(w.id)).length : 0;

  return (
    <div className="space-y-1">
      <label className="text-xs uppercase tracking-wide text-muted">{t("label")}</label>
      {loaded && owners.length === 0 ? (
        <p className="text-xs text-muted-soft">{t("noOwners")}</p>
      ) : (
        <Select
          value={person}
          onChange={setPerson}
          options={personOptions}
          placeholder={t("pickPerson")}
          className="w-full"
        />
      )}

      {aktuell && (
        <div
          data-testid="code-workspaces-list"
          className="max-h-40 overflow-y-auto overflow-x-hidden border border-border rounded-md px-3 py-2 space-y-1.5"
        >
          {aktuell.workspaces.length > 1 && (
            <Checkbox
              checked={vonPerson === aktuell.workspaces.length}
              indeterminate={vonPerson > 0 && vonPerson < aktuell.workspaces.length}
              onChange={alleUmschalten}
              label={t("all")}
              labelClassName="text-xs text-muted"
            />
          )}
          {aktuell.workspaces.map((w) => (
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

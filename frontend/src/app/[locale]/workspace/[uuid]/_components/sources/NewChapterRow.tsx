import { useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { X } from "@phosphor-icons/react";
import IconButton from "@/components/ui/IconButton";

/** The input row for a new chapter, it keeps a typed name across an Escape. */
export function NewChapterRow({
  open,
  onClose,
  onCreate,
}: {
  open: boolean;
  onClose: () => void;
  onCreate: (name: string) => Promise<void>;
}) {
  const t = useTranslations("workspace.detail.sources");
  const inputRef = useRef<HTMLInputElement>(null);
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!open) return;
    setError(null);
    inputRef.current?.focus();
  }, [open]);

  async function commit() {
    if (busy) return;
    const next = name.trim();
    if (!next) { onClose(); setError(null); return; }
    setBusy(true);
    try {
      await onCreate(next);
      onClose();
      setName("");
      setError(null);
    } catch (e) {
      setError(e instanceof Error && e.message ? e.message : t("chapterCreateFailed"));
    } finally {
      setBusy(false);
    }
  }

  if (!open) return null;
  return (
    <div
      className="relative px-3 py-2 flex items-center gap-2 flex-shrink-0"
      style={{ backgroundColor: "var(--surface-dim)", borderBottom: "1px solid var(--border)" }}
    >
      <input
        ref={inputRef}
        value={name}
        disabled={busy}
        placeholder={t("chapterNamePlaceholder")}
        onChange={(e) => setName(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter") { e.preventDefault(); commit(); }
          if (e.key === "Escape") { e.preventDefault(); onClose(); setError(null); }
        }}
        className="flex-1 min-w-0 text-sm px-2 py-1 rounded-md border-2 bg-background"
        style={{ borderColor: "var(--kb)", color: "var(--foreground)" }}
      />
      <button
        type="button"
        onClick={commit}
        disabled={busy}
        className="px-3 py-1.5 text-sm rounded-lg btn-primary flex-shrink-0"
      >
        {t("chapterCreate")}
      </button>
      <IconButton
        onClick={() => { onClose(); setName(""); setError(null); }}
        disabled={busy}
        aria-label={t("cancel")}
        title={t("cancel")}
      >
        <X size={13} weight="bold" />
      </IconButton>
      {error && (
        <div
          className="absolute left-3 right-3 top-full z-10 mt-1 rounded-lg px-3 py-2 text-xs leading-snug shadow-lg"
          style={{ backgroundColor: "#FEF2F2", border: "1px solid var(--error-border)", color: "var(--error-strong)" }}
        >
          {error}
        </div>
      )}
    </div>
  );
}

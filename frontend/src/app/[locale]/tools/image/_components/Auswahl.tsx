"use client";

interface Option<T extends string> {
  key: T;
  label: string;
}

interface Props<T extends string> {
  label: string;
  optionen: ReadonlyArray<Option<T>>;
  wert: T;
  onChange: (wert: T) => void;
  disabled?: boolean;
  hinweis?: string;
}

/** One row of choices in the style of the tool's size buttons, exactly one is active. */
export default function Auswahl<T extends string>({ label, optionen, wert, onChange, disabled, hinweis }: Props<T>) {
  return (
    <div className="mb-4">
      <p className="text-sm font-medium text-foreground-soft mb-2">{label}</p>
      <div className="flex flex-wrap gap-2" role="radiogroup" aria-label={label}>
        {optionen.map((o) => (
          <button
            key={o.key}
            type="button"
            role="radio"
            aria-checked={wert === o.key}
            disabled={disabled}
            onClick={() => onChange(o.key)}
            className={`px-3 py-1.5 text-xs font-medium rounded-md border-2 transition-colors disabled:opacity-50 disabled:cursor-not-allowed ${
              wert === o.key
                ? "border-kb bg-kb/10 text-kb dark:text-foreground"
                : "border-border text-foreground-soft hover:border-kb"
            }`}
          >
            {o.label}
          </button>
        ))}
      </div>
      {hinweis && <p className="mt-1.5 text-xs text-muted">{hinweis}</p>}
    </div>
  );
}

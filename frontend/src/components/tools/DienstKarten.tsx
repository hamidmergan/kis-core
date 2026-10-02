"use client";

export interface DienstKarte {
  id: string;
  anbieter: string;
  /** The voice or voices, already worded. */
  stimme: string;
  /** Marked as self-hosted, empty for outside services. */
  selbst?: string;
}

/** One card per voice service in a sample comparison, the chosen one filled like an active tab. */
export default function DienstKarten({
  karten,
  aktiv,
  onWahl,
  ariaLabel,
}: {
  karten: DienstKarte[];
  aktiv: string;
  onWahl: (id: string) => void;
  ariaLabel: string;
}) {
  return (
    <div className="mb-4 grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-5" role="radiogroup" aria-label={ariaLabel}>
      {karten.map((k) => {
        const gewaehlt = k.id === aktiv;
        return (
          <button
            key={k.id}
            type="button"
            role="radio"
            aria-checked={gewaehlt}
            onClick={() => onWahl(k.id)}
            className={`flex flex-col items-start justify-start text-left rounded-lg border-2 transition-colors px-3 py-2 ${
              gewaehlt ? "border-kb bg-kb/10" : "border-border hover:border-kb"
            }`}
          >
            <p className={`text-sm font-semibold ${gewaehlt ? "text-kb" : "text-foreground"}`}>{k.anbieter}</p>
            {k.stimme && <p className="text-xs text-muted">{k.stimme}</p>}
            {k.selbst && <p className="mt-1 text-xs text-kb-dark">{k.selbst}</p>}
          </button>
        );
      })}
    </div>
  );
}

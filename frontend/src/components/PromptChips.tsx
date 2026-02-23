const CHIPS = [
  "Kurze Sätze",
  "Formelle Sprache",
  "Für Studierende verständlich",
  "Technische Details betonen",
  "Übergänge zwischen Folien einfügen",
  "Mit Begrüßung beginnen",
];

interface PromptChipsProps {
  onChipClick: (chip: string) => void;
  disabled?: boolean;
}

export default function PromptChips({ onChipClick, disabled }: PromptChipsProps) {
  return (
    <div className="flex flex-wrap gap-2 mt-3" aria-label="Schnellauswahl">
      {CHIPS.map((chip) => (
        <button
          key={chip}
          type="button"
          onClick={() => onChipClick(chip)}
          disabled={disabled}
          className="px-3 py-1 text-xs rounded-full border border-[#0066cc] text-[#0066cc] hover:bg-[#e8f0fb] transition-colors disabled:opacity-40 disabled:cursor-not-allowed focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#0066cc]"
        >
          {chip}
        </button>
      ))}
    </div>
  );
}

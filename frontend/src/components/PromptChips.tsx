const SCRIPT_CHIPS = [
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
  chips?: string[];
}

export default function PromptChips({ onChipClick, disabled, chips }: PromptChipsProps) {
  const items = chips ?? SCRIPT_CHIPS;
  return (
    <div className="flex flex-wrap gap-2 mt-3" aria-label="Schnellauswahl">
      {items.map((chip) => (
        <button
          key={chip}
          type="button"
          onClick={() => onChipClick(chip)}
          disabled={disabled}
          className="px-3 py-1 text-xs rounded-full border border-[#004261] text-[#004261] hover:bg-[#e8f0fb] transition-colors disabled:opacity-40 disabled:cursor-not-allowed focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#004261]"
        >
          {chip}
        </button>
      ))}
    </div>
  );
}

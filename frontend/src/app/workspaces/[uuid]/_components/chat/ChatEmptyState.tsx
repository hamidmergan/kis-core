import { Chat } from "@phosphor-icons/react";


const EMPTY_PROMPTS = [
  "Gib mir einen Überblick über den Inhalt.",
  "Fasse die wichtigsten Punkte zusammen.",
  "Erkläre zentrale Begriffe kurz und verständlich.",
];


interface ChatEmptyStateProps {
  activeSourceIds: string[];
  onSendPrompt?: (text: string) => void;
}


export function ChatEmptyState({ activeSourceIds, onSendPrompt }: ChatEmptyStateProps) {
  const disabled = activeSourceIds.length === 0;
  return (
    <div className="flex-1 flex flex-col items-center justify-center gap-4 py-16">
      <div
        className="w-12 h-12 rounded-full flex items-center justify-center"
        style={{ backgroundColor: "rgba(var(--kb-rgb),0.08)" }}
      >
        <Chat size={22} style={{ color: "var(--kb)" }} />
      </div>
      <p className="text-sm font-medium" style={{ color: "var(--text)" }}>
        Dein KI-Assistent
      </p>
      <p className="text-xs text-center max-w-xs" style={{ color: "var(--muted)" }}>
        Wähle Quellen links aus – stell Fragen, lass dir Inhalte erklären oder gib Anweisungen.
      </p>
      <div className="flex flex-col gap-2 mt-2 w-full max-w-sm">
        {EMPTY_PROMPTS.map((prompt) => (
          <button
            key={prompt}
            disabled={disabled}
            onClick={() => onSendPrompt?.(prompt)}
            className="text-left text-xs px-4 rounded-xl border transition-all"
            style={{
              height: 50,
              borderColor: disabled ? "var(--border)" : "rgba(var(--kb-rgb),0.25)",
              color: disabled ? "var(--muted)" : "var(--text)",
              backgroundColor: "transparent",
              cursor: disabled ? "default" : "pointer",
              opacity: disabled ? 0.5 : 1,
            }}
            onMouseEnter={(e) => {
              if (!disabled) {
                e.currentTarget.style.backgroundColor = "rgba(var(--kb-rgb),0.10)";
                e.currentTarget.style.borderColor = "rgba(var(--kb-rgb),0.4)";
              }
            }}
            onMouseLeave={(e) => {
              if (!disabled) {
                e.currentTarget.style.backgroundColor = "transparent";
                e.currentTarget.style.borderColor = "rgba(var(--kb-rgb),0.25)";
              }
            }}
          >
            {prompt}
          </button>
        ))}
      </div>
    </div>
  );
}

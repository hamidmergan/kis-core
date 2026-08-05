import { useTranslations } from "next-intl";
import Mascot, { type MascotVariant } from "@/components/ui/Mascot";


interface ChatEmptyStateProps {
  activeSourceIds: string[];
  onSendPrompt?: (text: string) => void;
  variant?: MascotVariant;
}


export function ChatEmptyState({ activeSourceIds, onSendPrompt, variant = "francis" }: ChatEmptyStateProps) {
  const t = useTranslations("workspace.detail.chat");
  const disabled = activeSourceIds.length === 0;
  const prompts = [
    t("emptyPromptOverview"),
    t("emptyPromptSummary"),
    t("emptyPromptTerms"),
  ];
  return (
    <div className="flex-1 flex flex-col items-center justify-center gap-4 py-16">
      <Mascot variant={variant} size={120} state="wave" />
      <p className="text-base font-medium" style={{ color: "var(--foreground)" }}>
        {variant === "hilde" ? t("emptyHildeGreeting") : t("emptyFrancisGreeting")}
      </p>
      <p className="text-sm text-center max-w-xs" style={{ color: "var(--muted)" }}>
        {t("emptyHildeIntro")}
      </p>
      <div className="flex flex-col gap-2 mt-2 w-full max-w-sm">
        {prompts.map((prompt) => (
          <button
            key={prompt}
            disabled={disabled}
            onClick={() => onSendPrompt?.(prompt)}
            className="text-left text-sm px-4 rounded-xl border transition-colors btn-ghost"
            style={{
              height: 50,
              borderColor: disabled ? "var(--border)" : "rgba(var(--kb-rgb),0.25)",
              color: disabled ? "var(--muted)" : "var(--foreground)",
              cursor: disabled ? "default" : "pointer",
              opacity: disabled ? 0.5 : 1,
            }}
          >
            {prompt}
          </button>
        ))}
      </div>
    </div>
  );
}

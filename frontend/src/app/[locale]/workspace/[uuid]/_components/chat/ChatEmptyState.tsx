import { useTranslations } from "next-intl";
import { Chat } from "@phosphor-icons/react";
import Hilde from "@/components/ui/Hilde";


interface ChatEmptyStateProps {
  activeSourceIds: string[];
  onSendPrompt?: (text: string) => void;
  hildeEnabled?: boolean;
}


export function ChatEmptyState({ activeSourceIds, onSendPrompt, hildeEnabled = true }: ChatEmptyStateProps) {
  const t = useTranslations("workspace.detail.chat");
  const disabled = activeSourceIds.length === 0;
  const prompts = [
    t("emptyPromptOverview"),
    t("emptyPromptSummary"),
    t("emptyPromptTerms"),
  ];
  return (
    <div className="flex-1 flex flex-col items-center justify-center gap-4 py-16">
      {hildeEnabled ? (
        <Hilde size={120} state="wave" />
      ) : (
        <div
          className="w-12 h-12 rounded-full flex items-center justify-center"
          style={{ backgroundColor: "rgba(var(--kb-rgb),0.08)" }}
        >
          <Chat size={22} style={{ color: "var(--kb)" }} />
        </div>
      )}
      <p className="text-base font-medium" style={{ color: "var(--foreground)" }}>
        {hildeEnabled ? t("emptyHildeGreeting") : t("emptyAssistantTitle")}
      </p>
      <p className="text-sm text-center max-w-xs" style={{ color: "var(--muted)" }}>
        {hildeEnabled ? t("emptyHildeIntro") : t("emptyAssistantIntro")}
      </p>
      <div className="flex flex-col gap-2 mt-2 w-full max-w-sm">
        {prompts.map((prompt) => (
          <button
            key={prompt}
            disabled={disabled}
            onClick={() => onSendPrompt?.(prompt)}
            className="text-left text-sm px-4 rounded-xl border transition-colors enabled:hover:bg-[rgba(var(--kb-rgb),0.10)] enabled:hover:border-[rgba(var(--kb-rgb),0.4)]"
            style={{
              height: 50,
              borderColor: disabled ? "var(--border)" : "rgba(var(--kb-rgb),0.25)",
              color: disabled ? "var(--muted)" : "var(--foreground)",
              backgroundColor: "transparent",
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

import { useTranslations } from "next-intl";
import Mascot, { type MascotVariant } from "@/components/ui/Mascot";


interface ChatEmptyStateProps {
  activeSourceIds: string[];
  onSendPrompt?: (text: string) => void;
  variant?: MascotVariant;
}


export function ChatEmptyState({ variant = "francis" }: ChatEmptyStateProps) {
  const t = useTranslations("workspace.detail.chat");
  return (
    <div className="flex-1 flex flex-col items-center justify-center gap-4 py-16">
      <Mascot variant={variant} size={120} state="wave" />
      <p className="text-base font-medium" style={{ color: "var(--foreground)" }}>
        {variant === "hilde" ? t("emptyHildeGreeting") : t("emptyFrancisGreeting")}
      </p>
      <p className="text-sm text-center max-w-xs" style={{ color: "var(--muted)" }}>
        {t("emptyHildeIntro")}
      </p>
    </div>
  );
}

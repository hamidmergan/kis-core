import type { MyJob } from "../_types";


interface StatusBadgeProps {
  status: MyJob["status"];
  expired: boolean;
  isGeneratingScripts?: boolean;
}


export function StatusBadge({ status, expired, isGeneratingScripts }: StatusBadgeProps) {
  if (expired)
    return <span className="inline-flex text-xs font-medium text-muted-soft bg-surface px-2 py-0.5 rounded-full">Abgelaufen</span>;
  if (status === "success")
    return <span className="inline-flex text-xs font-medium text-success-strong bg-success-bg px-2 py-0.5 rounded-full">Fertig</span>;
  if (status === "failed")
    return <span className="inline-flex text-xs font-medium text-error-strong bg-error-bg px-2 py-0.5 rounded-full">Fehler</span>;
  if (status === "running" || isGeneratingScripts)
    return <span className="inline-flex text-xs font-medium text-info-strong bg-info-bg px-2 py-0.5 rounded-full animate-pulse">Läuft</span>;
  if (status === "awaiting_user")
    return <span className="inline-flex text-xs font-medium text-warn-strong bg-warn-bg px-2 py-0.5 rounded-full">Eingabe erforderlich</span>;
  if (status === "queued")
    return <span className="inline-flex text-xs font-medium text-info-strong bg-info-bg px-2 py-0.5 rounded-full">In der Schlange</span>;
  return <span className="inline-flex text-xs font-medium text-warn-strong bg-warn-bg px-2 py-0.5 rounded-full">Wartend</span>;
}

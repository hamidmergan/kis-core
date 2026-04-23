import type { MyJob } from "../_types";


interface StatusBadgeProps {
  status: MyJob["status"];
  expired: boolean;
  isGeneratingScripts?: boolean;
}


export function StatusBadge({ status, expired, isGeneratingScripts }: StatusBadgeProps) {
  if (expired)
    return <span className="inline-flex text-xs font-medium text-gray-400 bg-gray-100 px-2 py-0.5 rounded-full">Abgelaufen</span>;
  if (status === "success")
    return <span className="inline-flex text-xs font-medium text-green-700 bg-green-100 px-2 py-0.5 rounded-full">Fertig</span>;
  if (status === "failed")
    return <span className="inline-flex text-xs font-medium text-red-700 bg-red-100 px-2 py-0.5 rounded-full">Fehler</span>;
  if (status === "running" || isGeneratingScripts)
    return <span className="inline-flex text-xs font-medium text-blue-700 bg-blue-100 px-2 py-0.5 rounded-full animate-pulse">Läuft</span>;
  if (status === "awaiting_user")
    return <span className="inline-flex text-xs font-medium text-orange-700 bg-orange-100 px-2 py-0.5 rounded-full">Eingabe erforderlich</span>;
  if (status === "queued")
    return <span className="inline-flex text-xs font-medium text-purple-700 bg-purple-100 px-2 py-0.5 rounded-full">In der Schlange</span>;
  return <span className="inline-flex text-xs font-medium text-yellow-700 bg-yellow-100 px-2 py-0.5 rounded-full">Wartend</span>;
}

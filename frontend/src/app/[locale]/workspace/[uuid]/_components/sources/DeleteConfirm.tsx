import { useTranslations } from "next-intl";

/** Asks before a source or a chapter is deleted. */
export function DeleteConfirm({
  title,
  name,
  warning,
  warningClassName,
  onCancel,
  onConfirm,
}: {
  title: string;
  name: string;
  warning: string;
  /** Red when something is lost, soft when not. */
  warningClassName: string;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  const t = useTranslations("workspace.detail.sources");
  return (
    <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4">
      <div className="bg-background rounded-xl shadow-xl max-w-sm w-full p-6">
        <h3 className="text-base font-semibold mb-2">{title}</h3>
        <p className="text-sm text-foreground-soft mb-1 break-all">
          <span className="font-medium">{name}</span>
        </p>
        <p className={`text-sm ${warningClassName} mb-6`}>
          {warning}
        </p>
        <div className="flex gap-3 justify-end">
          <button
            onClick={onCancel}
            className="btn-cancel px-4 py-2 text-sm btn-secondary rounded-lg"
          >
            {t("cancel")}
          </button>
          <button
            onClick={onConfirm}
            className="px-4 py-2 text-sm btn-danger rounded-lg"
          >
            {t("delete")}
          </button>
        </div>
      </div>
    </div>
  );
}

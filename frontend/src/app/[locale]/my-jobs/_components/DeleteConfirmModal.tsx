import { useTranslations } from "next-intl";
import type { MyJob } from "../_types";


interface DeleteConfirmModalProps {
  job: MyJob;
  deleting: boolean;
  onCancel: () => void;
  onConfirm: () => void;
}


export function DeleteConfirmModal({ job, deleting, onCancel, onConfirm }: DeleteConfirmModalProps) {
  const t = useTranslations("myJobs.deleteModal");
  return (
    <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4">
      <div className="bg-background rounded-xl shadow-xl max-w-sm w-full p-6">
        <h3 className="text-base font-semibold mb-2">{t("title")}</h3>
        <p className="text-sm text-foreground-soft mb-1">
          <span className="font-medium">{job.tool_label}</span> - {job.original_filename}
        </p>
        <p className="text-sm text-error mb-6">
          {t("warning")}
        </p>
        <div className="flex gap-3 justify-end">
          <button
            onClick={onCancel}
            disabled={deleting}
            className="btn-cancel px-4 py-2 text-sm btn-secondary rounded-lg disabled:opacity-50"
          >
            {t("cancel")}
          </button>
          <button
            onClick={onConfirm}
            disabled={deleting}
            className="px-4 py-2 text-sm btn-danger rounded-lg disabled:opacity-50"
          >
            {deleting ? "..." : t("confirm")}
          </button>
        </div>
      </div>
    </div>
  );
}

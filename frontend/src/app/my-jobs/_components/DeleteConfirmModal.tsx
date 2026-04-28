import type { MyJob } from "../_types";


interface DeleteConfirmModalProps {
  job: MyJob;
  deleting: boolean;
  onCancel: () => void;
  onConfirm: () => void;
}


export function DeleteConfirmModal({ job, deleting, onCancel, onConfirm }: DeleteConfirmModalProps) {
  return (
    <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-xl shadow-xl max-w-sm w-full p-6">
        <h3 className="text-base font-semibold mb-2">Job löschen?</h3>
        <p className="text-sm text-gray-600 mb-1">
          <span className="font-medium">{job.tool_label}</span> – {job.original_filename}
        </p>
        <p className="text-sm text-red-600 mb-6">
          Der Job wird vollständig entfernt und ist nicht mehr herunterladbar.
        </p>
        <div className="flex gap-3 justify-end">
          <button
            onClick={onCancel}
            disabled={deleting}
            className="px-4 py-2 text-sm text-gray-700 border border-gray-300 rounded-lg hover:bg-gray-100 disabled:opacity-50"
          >
            Abbrechen
          </button>
          <button
            onClick={onConfirm}
            disabled={deleting}
            className="px-4 py-2 text-sm text-white bg-red-600 hover:bg-red-700 rounded-lg disabled:opacity-50"
          >
            {deleting ? "..." : "Löschen"}
          </button>
        </div>
      </div>
    </div>
  );
}

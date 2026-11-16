"use client";

import { useTranslations } from "next-intl";
import Spinner from "@/components/ui/Spinner";
import JobCancelButton from "./JobCancelButton";

/** Submit button with spinner, cancel next to it while the job runs, and the two notes below. */
export default function JobSubmitRow({ onSubmit, onCancel, canSubmit, processing, label, stallMessage, errorMessage }: {
  onSubmit: () => void;
  onCancel: () => void;
  canSubmit: boolean;
  processing: boolean;
  label: string;
  stallMessage: string;
  errorMessage: string;
}) {
  const tCommon = useTranslations("common");
  return (
    <>
      <div className="mb-6 flex items-center gap-3">
        <button
          onClick={onSubmit}
          disabled={!canSubmit || processing}
          className="self-start px-5 py-2 btn-primary text-sm font-medium rounded-md  focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-kb transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
        >
          {processing && (
            <Spinner size="sm" color="current" />
          )}
          {processing ? tCommon("processing") : label}
        </button>
        {processing && <JobCancelButton onClick={onCancel} />}
      </div>

      {stallMessage && !errorMessage && (
        <p className="text-sm text-warn" role="status">{stallMessage}</p>
      )}

      {errorMessage && (
        <p className="text-sm text-error" role="alert">{errorMessage}</p>
      )}
    </>
  );
}

import { useCallback, useState, type DragEvent } from "react";
import { useTranslations } from "next-intl";

interface UseFileDropzoneOptions {
  acceptedExtensions: string[];
  errorMessage?: string;
}

export function useFileDropzone({ acceptedExtensions, errorMessage }: UseFileDropzoneOptions) {
  const t = useTranslations("common");
  const [file, setFile] = useState<File | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);

  const selectFile = useCallback(
    (f: File) => {
      setFileError(null);
      const ext = "." + f.name.split(".").pop()?.toLowerCase();
      if (!acceptedExtensions.includes(ext)) {
        setFileError(errorMessage ?? t("onlyExtsAllowed", { exts: acceptedExtensions.join(", ") }));
        return;
      }
      setFile(f);
    },
    [acceptedExtensions, errorMessage, t],
  );

  const onDragOver = useCallback((e: DragEvent) => {
    e.preventDefault();
    setDragOver(true);
  }, []);

  const onDragLeave = useCallback((e: DragEvent) => {
    e.preventDefault();
    setDragOver(false);
  }, []);

  const onDrop = useCallback(
    (e: DragEvent) => {
      e.preventDefault();
      setDragOver(false);
      const f = e.dataTransfer.files?.[0];
      if (f) selectFile(f);
    },
    [selectFile],
  );

  const reset = useCallback(() => {
    setFile(null);
    setFileError(null);
    setDragOver(false);
  }, []);

  return {
    file,
    fileError,
    dragOver,
    selectFile,
    onDragOver,
    onDragLeave,
    onDrop,
    reset,
    setFileError,
  };
}

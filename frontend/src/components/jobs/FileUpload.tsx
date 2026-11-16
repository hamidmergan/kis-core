"use client";

import { useTranslations } from "next-intl";
import { MAX_UPLOAD_MB, MAX_UPLOAD_BYTES } from "@/lib/constants";
import FileDropzone from "./FileDropzone";

const ACCEPTED_EXTENSIONS = [".docx", ".pptx", ".md", ".tex", ".txt"];

interface FileUploadProps {
  onFileSelected: (file: File) => void;
  disabled?: boolean;
  selectedFilename?: string;
}

export default function FileUpload(props: FileUploadProps) {
  const t = useTranslations("common");
  return (
    <FileDropzone
      {...props}
      extensions={ACCEPTED_EXTENSIONS}
      maxMb={MAX_UPLOAD_MB}
      maxBytes={MAX_UPLOAD_BYTES}
      ariaLabel={t("fileSelectAria")}
    />
  );
}

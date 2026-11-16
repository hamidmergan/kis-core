"use client";

import { useTranslations } from "next-intl";
import { MAX_UPLOAD_MB, MAX_UPLOAD_BYTES } from "@/lib/constants";
import FileDropzone from "./FileDropzone";

const ACCEPTED_EXTENSIONS = [".docx", ".md", ".txt"];

interface TtsFileUploadProps {
  onFileSelected: (file: File) => void;
  disabled?: boolean;
  selectedFilename?: string;
}

export default function TtsFileUpload(props: TtsFileUploadProps) {
  const tUpload = useTranslations("tools.tts.upload");
  return (
    <FileDropzone
      {...props}
      extensions={ACCEPTED_EXTENSIONS}
      maxMb={MAX_UPLOAD_MB}
      maxBytes={MAX_UPLOAD_BYTES}
      ariaLabel={tUpload("selectFileAria")}
    />
  );
}

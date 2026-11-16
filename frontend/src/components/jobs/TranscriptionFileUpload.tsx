"use client";

import { useTranslations } from "next-intl";
import { MAX_TRANSCRIPTION_MB, MAX_TRANSCRIPTION_BYTES, MAX_TRANSCRIPTION_MINUTES } from "@/lib/constants";
import { exceedsTranscriptionLimit, readMediaDurationSeconds } from "@/lib/mediaDuration";
import FileDropzone from "./FileDropzone";

// Everything Whisper accepts, display and error text read from the same list.
const ALLOWED_EXTENSIONS = [".mp3", ".mp4", ".m4a", ".wav", ".flac", ".ogg", ".oga", ".webm", ".mpeg", ".mpga"];

interface TranscriptionFileUploadProps {
  onFileSelected: (file: File) => void;
  disabled?: boolean;
  selectedFilename?: string;
}

export default function TranscriptionFileUpload(props: TranscriptionFileUploadProps) {
  const t = useTranslations("common");
  const tStt = useTranslations("tools.stt");

  // Saves a long upload that fails on the playing time in the end.
  const checkDuration = async (file: File): Promise<string | null> => {
    const seconds = await readMediaDurationSeconds(file);
    if (!exceedsTranscriptionLimit(seconds)) return null;
    return tStt("tooLong", {
      minutes: Math.round((seconds as number) / 60),
      maxMinutes: MAX_TRANSCRIPTION_MINUTES,
    });
  };

  return (
    <FileDropzone
      {...props}
      extensions={ALLOWED_EXTENSIONS}
      maxMb={MAX_TRANSCRIPTION_MB}
      maxBytes={MAX_TRANSCRIPTION_BYTES}
      ariaLabel={t("audioVideoSelectAria")}
      extraCheck={checkDuration}
    />
  );
}

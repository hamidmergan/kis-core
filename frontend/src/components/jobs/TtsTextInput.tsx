"use client";

import { TTS_MAX_CHARS } from "@/lib/constants";
import LimitedTextInput from "./LimitedTextInput";

interface TtsTextInputProps {
  value: string;
  onChange: (next: string) => void;
  disabled?: boolean;
}

export default function TtsTextInput(props: TtsTextInputProps) {
  return <LimitedTextInput namespace="tools.tts.textInput" id="tts-text" maxChars={TTS_MAX_CHARS} {...props} />;
}

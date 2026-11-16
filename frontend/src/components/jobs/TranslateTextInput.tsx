"use client";

import { TRANSLATE_MAX_CHARS } from "@/lib/constants";
import LimitedTextInput from "./LimitedTextInput";

interface TranslateTextInputProps {
  value: string;
  onChange: (next: string) => void;
  disabled?: boolean;
}

export default function TranslateTextInput(props: TranslateTextInputProps) {
  return <LimitedTextInput namespace="tools.translate.textInput" id="translate-text" maxChars={TRANSLATE_MAX_CHARS} {...props} />;
}

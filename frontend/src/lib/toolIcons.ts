import {
  BookOpen,
  ChatsCircle,
  Image as ImageIcon,
  Microphone,
  MicrophoneStage,
  MonitorPlay,
  SpeakerHigh,
  TextAlignLeft,
  Translate,
  type Icon,
} from "@phosphor-icons/react";
import type { ToolKey } from "./modules";

/** One icon per tool, kept apart from modules.ts so the routing tests never load React. */
export const TOOL_ICONS: Record<ToolKey, Icon> = {
  translation: Translate,
  interpreter: ChatsCircle,
  tts: SpeakerHigh,
  transcription: Microphone,
  image: ImageIcon,
  summary: TextAlignLeft,
  glossary: BookOpen,
  screencast: MonitorPlay,
  podcast: MicrophoneStage,
};

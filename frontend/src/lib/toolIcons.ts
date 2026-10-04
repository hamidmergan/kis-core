import {
  BookOpen,
  ChatsCircle,
  Image as ImageIcon,
  MapTrifold,
  Microphone,
  MicrophoneStage,
  MonitorPlay,
  Presentation,
  SpeakerHigh,
  TextAlignLeft,
  Translate,
  type Icon,
} from "@phosphor-icons/react";
import type { ToolKey } from "./modules";

/** One icon per tool, kept apart from modules.ts so the routing tests never load React. */
export const TOOL_ICONS: Record<ToolKey, Icon> = {
  campus: MapTrifold,
  translation: Translate,
  interpreter: ChatsCircle,
  tts: SpeakerHigh,
  transcription: Microphone,
  image: ImageIcon,
  summary: TextAlignLeft,
  glossary: BookOpen,
  screencast: MonitorPlay,
  podcast: MicrophoneStage,
  praesentation: Presentation,
};

import { Bird, Gift, Info, Lightbulb, QrCode, SquaresFour, Star, type Icon } from "@phosphor-icons/react";
import { TOOL_ICONS } from "@/lib/toolIcons";
import type { IconKey } from "@/lib/event/types";

export const EVENT_ICONS: Record<IconKey, Icon> = {
  ...TOOL_ICONS,
  francis: Bird,
  info: Info,
  gift: Gift,
  star: Star,
  lightbulb: Lightbulb,
  qrCode: QrCode,
  platform: SquaresFour,
};

export const ICON_KEYS = Object.keys(EVENT_ICONS) as IconKey[];

import { Bird, Gift, Info, Lightbulb, QrCode, Star, type Icon } from "@phosphor-icons/react";
import { TOOL_ICONS } from "@/lib/toolIcons";
import type { IconKey } from "./types";

export const MOCKUP_ICONS: Record<IconKey, Icon> = {
  ...TOOL_ICONS,
  francis: Bird,
  info: Info,
  gift: Gift,
  star: Star,
  lightbulb: Lightbulb,
  qrCode: QrCode,
};

export const ICON_KEYS = Object.keys(MOCKUP_ICONS) as IconKey[];

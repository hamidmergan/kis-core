"use client";

/** The tunable numbers of one tool, built from what the backend reports about them.
 *
 * The range of a number lives in services/tool_numbers.py and comes down with the
 * settings, so no limit is written twice. A tool that enters a number there only needs
 * its three texts under admin.toolNumbers.<key> here.
 */

import { useTranslations } from "next-intl";
import { useSetting, useSettingGroup, type SettingHandle } from "./SettingsProvider";
import { NumberSetting } from "./fields";

/** One number as the backend describes it. */
export interface ToolNumber {
  key: string;
  tool: string;
  default: number;
  min: number;
  max: number;
}

/** The numbers of one tool, empty while the settings are still loading. */
export function useToolNumbers(tool: string): ToolNumber[] {
  const { settings } = useSettingGroup([]);
  const alle = (settings?.tool_numbers ?? []) as ToolNumber[];
  return alle.filter((n) => n.tool === tool);
}

/** One field. Its own component, so the hook count never depends on the list length. */
function OneNumber({ spec }: { spec: ToolNumber }) {
  const t = useTranslations("admin.toolNumbers");
  const field: SettingHandle<number> = useSetting<number>(spec.key, spec.default);
  return (
    <NumberSetting
      field={field}
      title={t(`${spec.key}.title`)}
      hint={t(`${spec.key}.hint`)}
      unit={t(`${spec.key}.unit`)}
      min={spec.min}
      max={spec.max}
      outOfRange={t("outOfRange", { min: spec.min, max: spec.max })}
    />
  );
}

export default function ToolNumbers({ tool }: { tool: string }) {
  const zahlen = useToolNumbers(tool);
  return (
    <>
      {zahlen.map((spec) => (
        <OneNumber key={spec.key} spec={spec} />
      ))}
    </>
  );
}

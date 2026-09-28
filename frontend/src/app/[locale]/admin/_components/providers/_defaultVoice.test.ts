/** What the default voice field under speech output offers and shows. */
import { describe, expect, it } from "vitest";

import { defaultVoiceOptions, shownDefaultVoice } from "./_defaultVoice";
import type { Provider } from "./_types";

function anbieter(id: number, name: string, ...stimmen: string[]): Provider {
  return {
    id,
    name,
    protocol: "openai_compat",
    base_url: "https://example.org",
    capabilities: ["tts"],
    voices: stimmen.map((s) => ({ voice_id: s, name: s.toUpperCase(), language: "de" })),
    enabled: true,
    last_probed_at: null,
    probe_status: null,
    probe_error: null,
    api_key_set: false,
    api_key_last_chars: null,
    created_at: "",
    updated_at: "",
    concurrency: {},
  };
}

const MYLAB = anbieter(21, "THL myLab", "alloy", "nova");
const KOKORO = anbieter(89, "Kokoro", "af_heart", "de_anna");

describe("defaultVoiceOptions", () => {
  it("bietet nur die Stimmen des Sternanbieters an, ohne Anbieternamen", () => {
    expect(defaultVoiceOptions([MYLAB, KOKORO], 89)).toEqual([
      { value: "89:af_heart", label: "AF_HEART" },
      { value: "89:de_anna", label: "DE_ANNA" },
    ]);
  });

  it("bietet ohne Stern alle Stimmen mit Anbieternamen an", () => {
    expect(defaultVoiceOptions([MYLAB], null).map((o) => o.label)).toEqual(["THL myLab · ALLOY", "THL myLab · NOVA"]);
  });

  it("bietet alle an, wenn der Sternanbieter nicht in der Liste steht", () => {
    expect(defaultVoiceOptions([MYLAB, KOKORO], 7)).toHaveLength(4);
  });
});

describe("shownDefaultVoice", () => {
  const optionen = defaultVoiceOptions([MYLAB, KOKORO], 89);

  it("zeigt die gespeicherte Stimme des Sternanbieters", () => {
    expect(shownDefaultVoice(optionen, "89:de_anna", 89)).toEqual({ shown: "89:de_anna", orphaned: false });
  });

  it("zeigt ohne gespeicherte Stimme die erste", () => {
    expect(shownDefaultVoice(optionen, "", 89)).toEqual({ shown: "89:af_heart", orphaned: false });
  });

  it("nimmt eine Stimme eines anderen Anbieters still als nicht gewaehlt", () => {
    expect(shownDefaultVoice(optionen, "21:nova", 89)).toEqual({ shown: "89:af_heart", orphaned: false });
  });

  it("meldet eine verschwundene Stimme des Sternanbieters", () => {
    expect(shownDefaultVoice(optionen, "89:weg", 89)).toEqual({ shown: "89:af_heart", orphaned: true });
  });

  it("meldet ohne Stern jede verschwundene Stimme", () => {
    const alle = defaultVoiceOptions([MYLAB], null);
    expect(shownDefaultVoice(alle, "89:weg", null)).toEqual({ shown: "21:alloy", orphaned: true });
  });

  it("meldet eine verschwundene Stimme auch, wenn der Sternanbieter fehlt", () => {
    const alle = defaultVoiceOptions([MYLAB, KOKORO], 7);
    expect(shownDefaultVoice(alle, "89:weg", 7)).toEqual({ shown: "21:alloy", orphaned: true });
  });

  it("zeigt ohne jede Stimme ein leeres Feld", () => {
    expect(shownDefaultVoice([], "", 89)).toEqual({ shown: "", orphaned: false });
  });
});

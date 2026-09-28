/** Which voice the speech tools preselect from the server's voice list. */
import { describe, expect, it } from "vitest";

import { preselectedVoice } from "./_voiceDefault";

const MYLAB = { id: 21, name: "THL myLab", voices: [{ voice_id: "alloy", name: "Alloy", language: "en" }] };
const KOKORO = {
  id: 89,
  name: "Kokoro",
  voices: [
    { voice_id: "af_heart", name: "Heart", language: "en" },
    { voice_id: "de_anna", name: "Anna", language: "de" },
  ],
};

describe("preselectedVoice", () => {
  it("nimmt die Vorauswahl des Servers", () => {
    expect(preselectedVoice([KOKORO, MYLAB], { provider_id: 89, voice_id: "de_anna" })).toEqual({
      providerId: 89,
      voiceId: "de_anna",
    });
  });

  it("nimmt ohne Vorauswahl die erste Stimme des ersten Anbieters", () => {
    expect(preselectedVoice([MYLAB, KOKORO], undefined)).toEqual({ providerId: 21, voiceId: "alloy" });
  });

  it("ueberhoert eine Vorauswahl, die nicht in der Liste steht", () => {
    expect(preselectedVoice([MYLAB, KOKORO], { provider_id: 89, voice_id: "weg" })).toEqual({
      providerId: 21,
      voiceId: "alloy",
    });
  });

  it("waehlt einen Anbieter ohne Stimmen mit leerer Stimme", () => {
    expect(preselectedVoice([{ id: 5, name: "Stumm", voices: [] }], null)).toEqual({ providerId: 5, voiceId: "" });
  });

  it("gibt ohne Anbieter nichts vor", () => {
    expect(preselectedVoice([], { provider_id: 21, voice_id: "alloy" })).toBeNull();
  });
});

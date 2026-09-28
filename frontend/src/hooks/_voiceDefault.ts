import type { ProviderWithVoices } from "./useVoices";

/** The voice the server names as the admin's standard, as it arrives from the voice list. */
export type ServerDefaultVoice = { provider_id: number; voice_id: string } | null | undefined;

/** The server's standard voice while it is listed, otherwise the first voice of the first provider. */
export function preselectedVoice(
  providers: ProviderWithVoices[],
  fromServer: ServerDefaultVoice,
): { providerId: number; voiceId: string } | null {
  if (fromServer) {
    const named = providers.find((p) => p.id === fromServer.provider_id);
    if (named?.voices.some((v) => v.voice_id === fromServer.voice_id)) {
      return { providerId: named.id, voiceId: fromServer.voice_id };
    }
  }
  const first = providers[0];
  if (!first) return null;
  return { providerId: first.id, voiceId: first.voices[0]?.voice_id ?? "" };
}

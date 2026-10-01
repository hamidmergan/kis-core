# Providers and models

Under Providers & models sit the accesses to the AI providers and the question which function
uses which model, in two tabs.

## Providers

A provider needs a name, a protocol (OpenAI-compatible, DeepL, or Docling, fixed once created), a
base URL, and usually an API key. After saving, KIS shows only the last six characters of the key.

- **Capabilities**: leave empty and KIS determines them itself after saving.
- **Concurrent calls**: a separate upper limit per area (LLM, speech recognition, voices, images,
  embeddings, text recognition), empty means no limit. The chat with Francis does not count here,
  image analysis counts toward the LLM.
- **Voices**: for a TTS-capable provider, voices can be loaded automatically or entered by hand,
  with language and description, to preview.
- Per row: enable or disable, check reachability, edit, delete (warns which functions would then
  be missing). Through the menu: export/import (the key stays encrypted) and delete everything.
- Under each provider sits the context window per model in tokens, measured automatically. A
  hand-entered number holds, clearing the field measures again.

## Functions

Each function (chat, embeddings, image analysis, image generation, image edit, OCR,
speech-to-text, text-to-speech, document translation, transcript translation) shows every eligible
provider, each with its own model field.

- **First choice**: the star directly on the provider, needs an entered model first. Applies to
  every function, for text-to-speech it additionally sets the default voice.
- **Fallback**: selectable per function. If the first choice does not answer or refuses the call,
  the same call goes to the fallback. Only active providers with an OpenAI-compatible interface
  and an entered model are eligible, for embeddings only with the same model, for text-to-speech
  only with their own voices. For text-to-speech the voice never switches within a running job,
  at most on the next one. Without a configured fallback, nothing switches.
- If the first provider for the LLM is full, a call automatically shifts to the next provider with
  a model, in the order of the list. Images and voices never shift.
- **Fine-tuning** (temperature, top_p): hidden behind a checkbox, only for chat-like functions.
- For text-to-speech, image analysis, image generation, image edit, and document translation, the
  person chooses the provider in the service themselves. For podcast, presentation, and summary,
  they choose a reachable provider with a model, with the star as the default.
- Per row a lightning icon tests this selection, plus one button to test them all in turn. There
  is no preview and no test mode, every change applies immediately for everyone.

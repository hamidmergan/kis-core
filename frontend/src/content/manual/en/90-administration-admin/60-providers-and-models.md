# Providers and models

Under Providers & models sit the accesses to the AI providers and the question which function
uses which model, in two tabs.

## Providers

A provider needs a name, a protocol, an address, and usually a key. After saving, KIS shows only
the last six characters of the key. Concurrent calls can be capped per area, and for a voice
provider, voices can be loaded automatically or entered by hand. Per row: enable, check
reachability, edit, delete, plus export/import and delete everything in the menu.

## Functions

Each function (chat, image analysis, image generation, OCR, speech recognition, text-to-speech,
translation, ...) shows every eligible provider with its own model field.

- **First choice**: the star directly on the provider, for text-to-speech it also sets the
  default voice.
- **Fallback**: steps in when the first choice does not answer or refuses. For text-to-speech the
  voice never switches within a running job.
- If the first provider for the LLM is full, a call shifts to the next one with a model
  automatically. Images and voices never shift.
- For some functions the person chooses the provider in the service themselves, likewise for
  podcast, presentation, and summary, where the star is only the default.
- Per row, a test of the current selection. Every change applies immediately for everyone, there
  is no preview and no test mode.

# Screencast

Turns a PowerPoint file into a narrated video, in another language if you want.

![The screencast service](/manual/{lang}/tool-screencast.png)

## The eight steps

1. **Upload**: a .pptx file with, out of the box, at most 50 slides. The language is chosen here:
   the target language for the translation or, with Skip translation, the Narration language.
   Plus glossary and translation provider. The source language is detected.
2. **Translate** runs by itself, when skipping the step is left out.
3. **Review**: download the translated or adopted PPTX, correct it in PowerPoint and upload it
   again. The number of slides must stay the same. Slides whose text did not change in the
   translation are marked.
4. **Instructions**: where the scripts come from. AI generation from the slides, Enter manually,
   Import scripts as a JSON list or From the speaker notes of the file.
5. **Scripts**: check every text, change it or rework it with Francis. That is the step where the
   quality is decided. All scripts together may have 100,000 characters.
6. **Settings**: provider and voice, speed from 0.7x to 1.2x, pause between slides from 0 s to
   3 s, image quality and Add subtitles.
7. **Rendering**: voicing and video production, runs in the background.
8. **Done**: download the MP4 or everything as a ZIP.

## Additional material

With AI generation you can hand over material whose matching passages flow into the scripts of
the individual slides: up to 10 files or workspace sources, at most 500,000 characters together.
The same limits apply as for the summary.

## Subtitles

With Add subtitles the spoken text is recognised and placed into the video as a track, switched
on and off with CC in the player. Rendering takes a little longer because of it.

## After rendering

- **Re-voice single slides**: you tick the slides that should be spoken again, for example after
  a changed text or with a different voice. All others keep their audio.
- **Retry** after a failure keeps finished clips and audio, only the rest is redone.
- **Paused**: after several failed attempts the job waits for Continue.

## The demo

View demo in the first step opens the service with a prepared set of slides. Every step and
setting can be tried, your own files cannot be uploaded, and the result is always the prepared
sample video.

## How long it takes

By far the largest part of the waiting time goes into the narration. The job runs in the
background, the result waits under Jobs. How many jobs you may have open at the same time is in
the overview of the services.

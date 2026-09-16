# Speech to text

Writes audio and video down. Either as plain text or as subtitles with time stamps.

![The speech to text service](/manual/{lang}/tool-speech-to-text.png)

## Three output formats

- **TXT** is plain text without time stamps
- **VTT** is the subtitle format for Moodle and modern web players
- **SRT** is the subtitle format for classic players like VLC

## Editing afterwards

The finished transcript can be edited in the window before downloading. That pays off for proper
names and technical terms, which recognition rarely gets right.

## Limits

There is an upper limit for the length of the recording. If a file is too long, the service says
how many minutes are allowed. Split the recording in that case.

On silence, recognition models occasionally invent text. Read the result through before you pass
it on.

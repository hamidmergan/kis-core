# Audio to text

Writes audio and video down. Either as plain text or as subtitles with time stamps.

![The audio to text service](/manual/{lang}/tool-speech-to-text.png)

## What may be uploaded

Audio as MP3, M4A, WAV, FLAC, OGG, OGA or MPGA, video as MP4, WEBM or MPEG. A file may be 500 MB
in size and, out of the box, 100 minutes long. If it is longer, the service names the minutes
allowed, then split the recording. Both limits are set by the administration.

## Three output formats

- **TXT** is plain text without time stamps
- **VTT** is the subtitle format for Moodle and modern web players
- **SRT** is the subtitle format for classic players like VLC

If there are several providers for recognition, you pick one.

## While it runs

Long recordings run in parts, the display says which part is on.

## Editing afterwards

The finished transcript can be edited in the window before downloading. That pays off for proper
names and technical terms, which recognition rarely gets right.

On silence, recognition models occasionally invent text. Read the result through before you pass
it on.

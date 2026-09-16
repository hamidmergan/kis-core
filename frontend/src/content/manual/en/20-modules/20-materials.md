# Uploading materials

![An opened workspace with its three areas](/manual/{lang}/module-view.png)

The list of materials sits on the left. The **plus** opens a dialog: pick a file there, read in a
web page by link, or add a YouTube video with its transcript. Files can also be dragged straight
into the list. The **folder icon** creates groups.

## Which files work

- Documents: `.pdf`, `.docx`, `.pptx`
- Audio: `.mp3`, `.wav`, `.flac`, `.m4a`
- Video: `.mp4`, `.webm`

The file picker does not accept other formats.

## Web page by link

The page becomes a PDF that sits in the viewer like any other material. Its first page carries the link and the date it was fetched. If the link points straight at a PDF, that file is taken as it is, without that line.

What does not work:

- pages behind a login or a paywall
- subpages, you get exactly the one page in the link
- pages that build their text in the browser, they yield no readable text

The page is fetched once. If it changes, delete the material and read the link in again.

## YouTube video by link

The audio of a YouTube video must not be downloaded. So you provide the transcript yourself, and the
video plays in the viewer straight from YouTube.

How to get the transcript:

1. Open the video on YouTube.
2. Below the video click “more” and then “Show transcript”.
3. Timestamps have to be visible. If not: three-dot menu in the transcript and “Toggle timestamps”.
4. Select all the text in the transcript, copy it and paste it into the dialog.
5. Your own video: in YouTube Studio open the text under Subtitles and paste it. The content of a subtitle file in SRT or VTT format works as text too.

What does not work:

- videos without subtitles, the “Show transcript” button is missing then
- videos with embedding disabled
- age-restricted videos

The viewer asks once for the first YouTube video. Only after that click does the player load from
YouTube, no data goes to Google before. The click then holds for every YouTube video in this
browser, in other workspaces too.

## After the upload

A new file needs a moment. Until then a hint sits on it and it cannot be used yet. Video and
audio also get a transcript to read along, for YouTube videos it is the pasted one.

## The selection steers everything

Chat and exercises only use the **ticked** materials. A question about one lecture? Tick only
that one.

## Renaming and deleting

Through the three dots on the material. Deleting is final.

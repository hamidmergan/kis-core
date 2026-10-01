# Uploading materials

![An opened workspace with its three areas](/manual/{lang}/module-view.png)

The list of materials sits on the left. The **plus** opens a dialog: pick a file there, read in a
web page by link, or add a YouTube video with its transcript. Files can also be dragged straight
into the list. The **folder icon** next to it creates a chapter.

## Which files work

- Documents: `.pdf`, `.docx`, `.pptx`
- Audio: `.mp3`, `.wav`, `.flac`, `.m4a`
- Video: `.mp4`, `.webm`

The file picker does not accept other formats. A second material with the same name is refused.

## Limits

- **500 MB** per file
- **200 pages** per document and **500,000 characters** of text, longer ones are refused
- **50 materials** per workspace. The administration can change these three limits
- **30 files** at once, the rest is skipped
- If too many uploads are running at the moment, yours waits for a free slot and then starts by
  itself

## Chapters

Chapters structure the list. They are order only, for chat and tools the tick alone counts.

- The **tick on a chapter** sets the ticks of every file inside it
- The chapter menu: rename, move up or down, delete. The files are kept and sit under **No
  chapter** afterwards
- A material goes in through its own menu with **Move to chapter**
- Chapters can be collapsed, at most 100 per workspace

## Web page by link

The page becomes a PDF that sits in the viewer like any other material. Its first page carries the
link and the date it was fetched, and the file icon in the list gets a small globe. If the link
points straight at a PDF, that file is taken as it is, without that line, up to 50 MB.

What does not work:

- pages behind a login or a paywall
- subpages, you get exactly the one page in the link
- pages that build their text in the browser, they yield no readable text
- pages with fewer than 100 words of text

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
- videos over 240 minutes. Then paste only the part of the transcript you need

The viewer asks once for the first YouTube video. Only after that click does the player load from
YouTube, no data goes to Google before. The click then holds for every YouTube video in this
browser, in other workspaces too.

## After the upload

A new file needs a moment. Until then its stage sits on it, Parsing, OCR with the page number,
Chunking, Embedding, Summarizing, and it cannot be ticked yet. Video and audio also get a
transcript to read along, for YouTube videos it is the pasted one.

- If processing fails, the reason sits on the file together with a **Retry** button
- If pages with images could not be read, the file menu says **Text recognition incomplete** with
  the number of open pages. **Catch up text recognition** runs the file through again, this time
  with text recognition. The material is usable either way
- **What this is about** next to the file shows a short summary of the material, written during
  the upload

## The selection steers everything

Chat and tools only use the **ticked** materials. A question about one lecture? Tick only that one.

## A note for everyone

The **info icon** in the workspace header holds a note that everyone in the workspace reads: up
to 2,000 characters of text and up to 30 links with a label. Owners and tutors write it, for
everyone else the icon only appears once a note exists.

## The three panels

- Every panel can be **minimized** to a narrow strip and dragged wider or narrower
- A **double click** on a panel's header shows it alone, the other two shrink to strips. A second
  double click restores the previous layout

## Renaming and deleting

Through the three dots on the material. Deleting is final and also removes the dates that came
from the material into the schedule.

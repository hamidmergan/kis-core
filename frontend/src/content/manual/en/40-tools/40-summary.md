# Summary

Brings several sources together into one text, optionally following a fixed structure.

![The summary service](/manual/{lang}/tool-summary.png)

## Sources

Up to ten files per job, as PDF, Word, PowerPoint, text, Markdown, or subtitles. Per file
500,000 characters and 200 pages are possible, 5 million characters together. Only the
text layer is read. Scanned pages without text are left out, and a PDF with no text at all
is rejected with a message.

Each file goes into one call whole. If the chosen model cannot hold a file, the service
refuses the job with a message naming the file and the model. A larger model in the
provider picker solves that.

## Structure

Plain text, short briefing, study guide, timeline, or frequently asked questions. The
structure decides what is read out of the sources first and how the text is organized. The
number of sections depends on how much the sources contain.

## Duration

Every source is read once, then the text is written section by section. A law of a good 200
pages takes a few minutes, you can leave the page in the meantime, the job keeps running.

## The result

The text comes as Markdown and as a Word file with a cover page and a table of contents.
Statements carry the name of the file they come from.

## What to expect

A summary is a shortening and inevitably leaves something out. It does not replace the
original when accuracy matters.

## The difference to the chat inside a workspace

The service delivers a text to download. The chat inside a workspace works across all
ticked materials and backs every statement with the spot it came from.

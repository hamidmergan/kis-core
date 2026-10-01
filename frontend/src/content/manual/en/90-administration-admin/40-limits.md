# Limits

Under Limits sit every upper bound for size, volume, and context, in two tabs.

## Material

- **Services**: slides per screencast (200 by default, more slides mainly means a longer wait, a
  screencast aborts after two hours). Running jobs per person (5 by default, counted across all
  services, with services that have a voice such as text to audio, podcast, and screencast counted
  apart from the rest. -1 means unlimited). Kept jobs per person (100 by default, the only
  clean-up rule, a further job pushes out the oldest together with its file. -1 means only disk
  space is the limit).
- **AI assistant**: maximum materials per workspace (50 by default). Maximum characters per
  document (between 30,000 and 500,000, counted after reading in, an oversized document counts as
  failed rather than being cut short. At 500,000 every document fits on its own into podcast,
  presentation, and summary too).
- **Shared**: size of a file in MB (500 by default, applies to every uploaded file, for a podcast
  to all files of one job together). Maximum pages per material (200 by default, applies to
  materials in the workspace and to podcast, summary, and translation, media and screencast are
  unaffected). Length of a recording in minutes (100 by default, longer ones are automatically
  cut into pieces and recognised one by one).

## Context

- **Chat context budget for overview questions** and **for specific questions**: how much text
  the AI assistant Francis gives the model per question type, in characters, with a token count
  shown alongside.
- **Context budget of the tools**: how much text from the materials the tools may give the model.
  Mind map, podcast, schedule, and data table draw on the value in full, flashcards, vocab cards,
  quiz, vocabulary exercises, and grammar exercises take only as much as the ordered number of
  tasks needs. If the configured model cannot handle this value, it refuses the job, and only
  lowering the value helps.

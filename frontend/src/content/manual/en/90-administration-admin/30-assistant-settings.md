# Setting up the AI assistant

Under AI Assistant you decide how material is read in and how the language trainer works, in two
areas.

## Materials

- **OCR for scans and image pages**: on means pages heavy with images or scans run through text
  recognition on reading in, which costs one call per page and takes longer. Off means faster and
  cheaper, but such pages then stay empty in the search.
- **Language of the tools**: which language flashcards, quiz, data table, and mind map are
  written in. The language trainer does not follow this, it stays in German.
- **Reindex all materials**: recalculates every workspace's embeddings with the current provider,
  needed after switching the embedding model. Needs maintenance mode under System beforehand. A
  notice shows how many workspaces still carry a different model.
- **Clear the stocks**: exercise sets and schedule extractions, which arise from use and hang off
  the source rather than the workspace, can be thrown away platform-wide here. Finished exercise
  sets, progress, and entered dates stay, only what was prepared in the background is lost and is
  created again when needed.

## Language level

Two tabs.

**Assessment**

- **Language trainer**: the switch for the whole platform. Off means nobody is asked and the
  trainer appears nowhere. Decisions already made and levels already set stay saved and apply
  again once you switch it back on. Who actually sees the trainer additionally needs a right of
  its own in the rights matrix, which no system role carries by default.
- **Questions in the language test**: the question catalogue, 12 questions by default. Each
  question is either choice (click, with at least one correct answer) or free text (type it
  yourself). Free text with an entered solution is checked by code word for word, without a
  solution the AI judges the answer at the end. At least 2 free-text questions without a solution
  are required, only through them does the AI get a real writing sample. The test itself then runs
  without a single AI call, only the final level needs one. The whole question set can also be
  written once by the AI and then reviewed.

**AI behaviour**

- **Levels A1 to C2**: a description and example sentences per level, the basis for both the
  assessment and the adapted answers in chat.
- **Advanced**: the prompt texts for the test, chat, services, and tools, change only with the
  matching knowledge.

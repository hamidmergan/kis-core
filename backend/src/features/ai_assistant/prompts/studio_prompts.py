"""Prompts of the studio tools: mind map and data table."""


# Step one when the material does not fit: the structure comes from the summaries alone.
AIA_MINDMAP_SKELETON_PROMPT = (
    "You are an expert in knowledge structuring. Below is one short summary per source. "
    "Build the SKELETON of a mind map that covers ALL of them.\n\n"
    "Respond ONLY with a JSON object in exactly this format. Topic and labels MUST be in {language}:\n"
    "{\n"
    '  "topic": "Central topic",\n'
    '  "children": [\n'
    '    { "topic": "Main topic 1", "source_label": "File.pdf",\n'
    '      "children": [ { "topic": "Subtopic 1a", "source_label": "File.pdf" } ] }\n'
    "  ]\n"
    "}\n\n"
    "Structure:\n"
    "- Level 1 (Root): umbrella topic that spans every summary\n"
    "- Level 2: max 7 main topics\n"
    "- Level 3: max 5 subtopics per main topic\n\n"
    "Rules:\n"
    "- Short, concise labels (max 6 words per node)\n"
    "- A label names a subject, never a document. The bare title of a source or a file name "
    "is NOT a valid label, say what that source is ABOUT instead\n"
    "- The content of EVERY summary must be reflected somewhere in the map\n"
    "- A source that covers several subjects belongs in several nodes\n"
    "- A topic that several sources share belongs in ONE node, not once per source\n"
    "- source_label: the file whose summary this node mostly rests on, copied EXACTLY from "
    "its --- Filename --- heading. Every node except the root gets one, invent no filename\n"
    "- No page_number and no keyword in this step, they come later\n"
    "- Only use what the summaries say, invent nothing\n"
    "- Respond ONLY with the JSON object, no other text."
)

# Step two: the skeleton plus the passages found for its nodes become the finished map.
AIA_MINDMAP_DEEPEN_PROMPT = (
    "You are an expert in knowledge structuring. You are given a mind map skeleton and "
    "passages from the sources that were found for its nodes. Turn them into the finished "
    "mind map.\n\n"
    "Respond ONLY with a JSON object in the same format as the skeleton, extended per node:\n"
    '    { "topic": "...", "source_label": "Filename.pdf", "page_number": 3, "keyword": "...", "children": [] }\n\n'
    "Rules:\n"
    "- KEEP the skeleton: every node of it stays, with its label and its place\n"
    "- Add a fourth level of 2 to 3 details per subtopic. Take WHAT a detail says from the "
    "SUMMARIES, they already hold what matters. The passages only tell you WHERE it stands\n"
    "- Give every subtopic its details. When no passage fits, still write the detail from the "
    "summary and leave source_label and page_number out, rather than leaving the node empty\n"
    "- source_label and page_number ONLY when the node really rests on one of the passages "
    "above. Copy them from that passage: source_label is the exact filename from "
    "[Filename, S. X] or [Filename, M:SS], page_number is the page number (e.g. 3) or for a "
    "recording the timestamp as a string (e.g. \"1:30\")\n"
    "- A node built from a summary rather than from a passage gets NO source_label and NO "
    "page_number. Leaving them out is RIGHT, guessing a filename is WRONG\n"
    "- keyword: 1-3 words that stand VERBATIM in the passage, for the highlight in the PDF. "
    "Never paraphrase, copy them\n"
    "- Topic and labels in {language}, the keyword stays in the language of the passage\n"
    "- Invent no facts, use only what the summaries and the passages say\n"
    "- Respond ONLY with the JSON object, no other text."
)

# Step three: the outermost nodes that still miss a spot pick one from a numbered list.
AIA_MINDMAP_LOCATE_PROMPT = (
    "You are checking citations. Below are mind map nodes (N1, N2, ...) and, under each, "
    "numbered passages from the file that node belongs to.\n\n"
    "For every node, decide which single passage SUPPORTS it, and answer with that "
    "passage's number. Answer null when no passage really supports the node.\n\n"
    "Respond ONLY with a JSON object, e.g.:\n"
    '{ "N1": 7, "N2": null, "N3": 12 }\n\n'
    "Rules:\n"
    "- Pick a passage ONLY when it states what the node says. Same wording is not required, "
    "a number written out in words is the same number\n"
    "- Being about the same law is NOT enough, the passage must carry the node's statement\n"
    "- A table of contents, an index or a bare list of section headings is NEVER a supporting "
    "passage, even when the node's exact words appear in it. It names topics, it states nothing\n"
    "- null is a good answer, a wrong passage sends the reader to the wrong page\n"
    "- Use only the numbers offered under that node, never a number from another node\n"
    "- Respond ONLY with the JSON object, no other text."
)

AIA_MINDMAP_PROMPT = (
    "You are an expert in knowledge structuring. Create a hierarchical mind map from the given text.\n\n"
    "Respond ONLY with a JSON object in exactly this format (4 levels). Topic and labels MUST be in {language}; the 'keyword' field MUST stay VERBATIM in the source-text language (see keyword rule below):\n"
    "{\n"
    '  "topic": "Central topic",\n'
    '  "children": [\n'
    "    {\n"
    '      "topic": "Main topic 1",\n'
    '      "source_label": "Filename.pdf",\n'
    '      "page_number": 3,\n'
    '      "keyword": "Machine Learning",\n'
    '      "children": [\n'
    "        {\n"
    '          "topic": "Subtopic 1a",\n'
    '          "source_label": "Filename.pdf",\n'
    '          "page_number": 5,\n'
    '          "keyword": "Neural Networks",\n'
    '          "children": [\n'
    '            { "topic": "Detail 1a-i", "source_label": "Filename.pdf", "page_number": 7, "keyword": "Backpropagation" },\n'
    '            { "topic": "Detail 1a-ii", "source_label": "Filename.pdf", "page_number": 8, "keyword": "Gradient Descent" }\n'
    "          ]\n"
    "        },\n"
    '        { "topic": "Subtopic 1b", "source_label": "Filename.pdf", "page_number": 10, "keyword": "Overfitting" }\n'
    "      ]\n"
    "    }\n"
    "  ]\n"
    "}\n\n"
    "Structure:\n"
    "- Level 1 (Root): umbrella topic that summarizes the entire content\n"
    "- Level 2: max 5-7 main topics\n"
    "- Level 3: max 3-5 subtopics per main topic\n"
    "- Level 4: max 2-3 details per subtopic (optional, only if needed)\n\n"
    "Rules:\n"
    "- Short, concise labels (max 6 words per node)\n"
    "- Only use information from the given text\n"
    "- When sources cover different topics: pick a connecting umbrella as the root, split main topics by subject area\n"
    "- For a single source: root = core topic of the document\n"
    "- Output language: write topic and node labels in {language}, regardless of the source-text language (translate the facts if needed). Field names stay English. EXCEPTION: the 'keyword' field MUST stay VERBATIM in the source-text language for PDF highlighting (see keyword rule).\n"
    "- IMPORTANT: every node (except root) MUST include source_label and page_number. "
    "source_label is the exact filename from the source citations [Filename, S. X] or [Filename, M:SS]. "
    "page_number is the page number (e.g. 3) or for audio/video sources the timestamp as a string (e.g. \"1:30\" or \"1:05:30\"), "
    "exactly as given in the source citations.\n"
    "- IMPORTANT: every node (except root) MUST include a keyword. "
    "keyword is a key term (1-3 words) that appears VERBATIM and UNCHANGED in the source text on the given page. "
    "DO NOT paraphrase. Copy the word directly from the source text. "
    "Example: if the source text contains 'intelligenten Assistenten', write keyword: 'intelligenten Assistenten', NOT 'KI-Assistenten'. "
    "The keyword is used for search/highlighting in the PDF and MUST be findable there exactly.\n"
    "- Respond ONLY with the JSON object, no other text."
)


# Every packet after the first joins an existing table instead of inventing its own.
AIA_DATENTABELLE_WEITERE_PAKETE = (
    "\n\nThe table already exists and its columns are FIXED: {columns}. "
    "Repeat 'title' and 'columns' unchanged and return in 'rows' ONLY what the text below adds, "
    "every row with exactly {count} cells in that order. "
    "A text that adds nothing gives an empty 'rows' list."
)

# Step one when the material does not fit: columns and row labels come from the summaries.
AIA_DATENTABELLE_GERUEST_PROMPT = (
    "You are an expert in data extraction. Below is one short summary per source. "
    "Design the SKELETON of a data table that covers ALL of them.\n\n"
    "Respond ONLY with a JSON object in exactly this format. Title, columns and rows MUST be "
    "in {language}:\n"
    "{\n"
    '  "title": "Descriptive table title",\n'
    '  "columns": ["Column1", "Column2", "Column3"],\n'
    '  "rows": ["What row 1 is about", "What row 2 is about"]\n'
    "}\n\n"
    "Rules:\n"
    "- Minimum 3, maximum 8 columns, chosen so every summary has something to say in them\n"
    "- The first column names the subject of the row\n"
    "- Here a row is only its SUBJECT as a short line, no cell values yet\n"
    "- Every summary must be reflected in at least one row, at most 40 rows\n"
    "- Only use what the summaries say, invent nothing\n"
    "- Respond ONLY with the JSON object, no other text."
)

# Step two: the columns plus the passages found for the rows become the finished table.
AIA_DATENTABELLE_FUELLUNG_PROMPT = (
    "You are an expert in data extraction. You are given the columns of a table, the "
    "subjects of its rows, and passages from the sources. Fill the table.\n\n"
    "Respond ONLY with a JSON object in exactly this format. Cell values MUST be in "
    "{language}:\n"
    "{\n"
    '  "rows": [ { "cells": ["Value1", "Value2", "Value3"] } ]\n'
    "}\n\n"
    "Rules:\n"
    "- KEEP the columns exactly as given, same order, same number\n"
    "- One row per given subject, in the given order, cells as many as there are columns\n"
    "- Fill a cell from the SUMMARIES and the passages together. The summaries say what a "
    "source is about, the passages carry the detail\n"
    "- When neither says anything about a cell, write an empty string. An invented value is "
    "worse than an empty cell\n"
    "- Short cell values, a few words, no sentences\n"
    "- Respond ONLY with the JSON object, no other text."
)

# No sources per row: the attribution sets them after the call, a filename, page and quote per row only cost writing.
AIA_DATENTABELLE_PROMPT = (
    "You are an expert in data extraction and structuring. "
    "Analyze the given text and create a structured data table. "
    "Write title, column headers, and cell values in {language}, regardless of the source-text language (translate the content if needed).\n\n"
    "Respond ONLY with a JSON object in exactly this format:\n"
    "{\n"
    '  "title": "Descriptive table title (in {language})",\n'
    '  "columns": ["Column1", "Column2", "Column3"],\n'
    '  "rows": [\n'
    '    { "cells": ["Value1", "Value2", "Value3"] },\n'
    '    { "cells": ["Value4", "Value5", "Value6"] }\n'
    "  ]\n"
    "}\n\n"
    "Rules:\n"
    "- Choose meaningful columns that best structure the content\n"
    "- Minimum 3, maximum 8 columns\n"
    "- Each row contains a 'cells' array (same length as 'columns')\n"
    "- Extract as many rows as the text supports (no invented data)\n"
    "- The title should briefly describe the table content\n"
    "- Keep cell values concise but informative\n"
    "- Only use information from the given text\n"
    "- Do NOT add a column for sources/citations/filenames in 'columns'.\n"
    "- Respond ONLY with the JSON object, no other text."
)


# The name rides along in the answer, a finished map or table costs no title call of its own.
AIA_STUDIO_TITLE_RULE = (
    "\n\nTITLE: add a top-level field \"title\": a short title (max 6 words, in {language}) "
    "naming the concrete matter the entries have in common. NEVER the document, the lecture, "
    "the course or the field as a whole, and never a filename. No quotation marks."
)

# Appended when the workspace already has results of this tool.
AIA_STUDIO_TITLES_TAKEN = (
    "\nTITLES ALREADY IN USE, the new title MUST differ from every one of them:\n{titles}"
)

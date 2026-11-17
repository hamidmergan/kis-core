/** How a set title is shown: generated titles lose their tool prefix, the name itself stays. */
export function setDisplayTitle(title: string): string {
  return title
    .replace(/^(Lernkarten|Grammatik-Übung|Quiz)\s*(aus|von)\s*/i, "")
    .replace(/^(Flashcards|Grammar exercise|Quiz)\s*(from|of)\s*/i, "");
}

/** A set named after its file is shown without the file ending. */
export function withoutFileExtension(title: string): string {
  return title.replace(/\.(pdf|mp4|mp3|webm|wav|m4a|ogg)$/i, "");
}

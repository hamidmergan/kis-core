/**
 * Die Gruppen der Rechtetabelle in ihre Kapitel buendeln.
 *
 * Der Server liefert eine flache Liste in Anzeigereihenfolge, jede Gruppe mit
 * ihrem Kapitel. Hier entsteht daraus die zweite Ebene, ohne die Reihenfolge
 * anzutasten: gebuendelt wird nur, was ohnehin nebeneinander steht.
 */

export interface InChapter {
  chapter?: string;
}

export interface ChapterBlock<T> {
  chapter?: string;
  groups: T[];
}

export function byChapter<T extends InChapter>(groups: T[]): ChapterBlock<T>[] {
  const blocks: ChapterBlock<T>[] = [];
  for (const group of groups) {
    const open = blocks[blocks.length - 1];
    if (open && open.chapter === group.chapter) open.groups.push(group);
    else blocks.push({ chapter: group.chapter, groups: [group] });
  }
  return blocks;
}

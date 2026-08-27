/** Groups the permission table's groups into their chapters, without reordering. */

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

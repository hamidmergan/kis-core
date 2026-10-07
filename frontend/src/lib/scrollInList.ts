type Box = { top: number; height: number };

// Scroll position that puts the item in the middle of the list, clamped to the list's range.
export function centeredScrollTop(
  list: Box & { scrollTop: number; clientHeight: number; scrollHeight: number },
  item: Box,
): number {
  const itemTop = item.top - list.top + list.scrollTop;
  const target = itemTop - (list.clientHeight - item.height) / 2;
  return Math.max(0, Math.min(target, list.scrollHeight - list.clientHeight));
}

// Unlike scrollIntoView, this moves only the list, never a hidden-overflow parent or the page (iOS).
export function centerInList(list: HTMLElement, item: HTMLElement, behavior: ScrollBehavior = "smooth"): void {
  const lr = list.getBoundingClientRect();
  const ir = item.getBoundingClientRect();
  const top = centeredScrollTop(
    { top: lr.top, height: lr.height, scrollTop: list.scrollTop, clientHeight: list.clientHeight, scrollHeight: list.scrollHeight },
    { top: ir.top, height: ir.height },
  );
  list.scrollTo({ top, behavior });
}

// Which chip is active and which chip sites are open, at module scope so both survive a redraw.

import { useCallback, useSyncExternalStore } from "react";

// The target just jumped to.
let _activeChipTarget: string | null = null;
const _activeChipSubs = new Set<() => void>();

// The id of a chip: source plus page or second.
export function chipTargetKey(uuid: string, page: number, seconds: number | undefined): string {
  return seconds != null ? `${uuid}@t${seconds}` : `${uuid}@p${page}`;
}

export function setActiveChipTarget(key: string): void {
  if (_activeChipTarget === key) return;
  _activeChipTarget = key;
  _activeChipSubs.forEach((fn) => fn());
}

// For chips outside React, the mindmap draws its own frame from this.
export function getActiveChipTarget(): string | null {
  return _activeChipTarget;
}

export function subscribeActiveChip(cb: () => void): () => void {
  _activeChipSubs.add(cb);
  return () => { _activeChipSubs.delete(cb); };
}

// Takes the frame off the active chip when the viewer drops its own frame.
export function clearActiveChipTarget(): void {
  if (_activeChipTarget === null) return;
  _activeChipTarget = null;
  _activeChipSubs.forEach((fn) => fn());
}

export function useIsActiveChip(key: string): boolean {
  const getSnapshot = useCallback(() => _activeChipTarget === key, [key]);
  return useSyncExternalStore(subscribeActiveChip, getSnapshot, getSnapshot);
}


// Expanding is a toggle, the choice lives at module scope so it survives.
const _openChipGroups = new Set<string>();

// One entry per message drives the toggle for all its sites.
const _openAllOwners = new Set<string>();

// One subscriber list for both sets, a site has to re-read after either.
const _chipStateSubs = new Set<() => void>();
function notifyChipState(): void {
  _chipStateSubs.forEach((fn) => fn());
}

function subscribeChipState(cb: () => void): () => void {
  _chipStateSubs.add(cb);
  return () => { _chipStateSubs.delete(cb); };
}

function useChipFlag(getSnapshot: () => boolean): boolean {
  return useSyncExternalStore(subscribeChipState, getSnapshot, getSnapshot);
}

// The message a site belongs to, everything before the hash.
export function chipOwnerOf(groupId: string): string {
  const i = groupId.indexOf("#");
  return i < 0 ? groupId : groupId.slice(0, i);
}

/** Is this one site pinned open? */
export function useChipGroupPinned(groupId: string): boolean {
  return useChipFlag(useCallback(() => _openChipGroups.has(groupId), [groupId]));
}

export function setChipGroupPinned(groupId: string, pinned: boolean): void {
  if (pinned) _openChipGroups.add(groupId);
  else _openChipGroups.delete(groupId);
  notifyChipState();
}

/** Is the toggle of this message on? */
export function useAllChipsOpen(owner: string): boolean {
  return useChipFlag(useCallback(() => _openAllOwners.has(owner), [owner]));
}

/** Toggles the message, off really closes everything. */
export function toggleAllChips(owner: string): void {
  if (_openAllOwners.has(owner)) {
    _openAllOwners.delete(owner);
    // Deleting during the iteration is safe here.
    const prefix = `${owner}#`;
    _openChipGroups.forEach((id) => { if (id.startsWith(prefix)) _openChipGroups.delete(id); });
  } else {
    _openAllOwners.add(owner);
  }
  notifyChipState();
}

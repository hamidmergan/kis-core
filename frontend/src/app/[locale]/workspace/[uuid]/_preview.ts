export interface PreviewInput {
  /** Real relationship to this course, owner or tutor. */
  realIsOwner: boolean;
  isDemoWorkspace: boolean;
  /** Holds aia.workspace.create, so the owner side is one they can reach. */
  darfModuleAnlegen: boolean;
  /** null: nobody pressed the switch yet, then the default per course counts. */
  override: boolean | null;
}

export interface PreviewState {
  /** Switch offered at all. */
  canPreview: boolean;
  previewOn: boolean;
  /** What the interface goes by, the preview bends it. */
  isOwner: boolean;
  /** Owner elements shown, but marked and switched off. */
  ownerPreview: boolean;
  /** true: looks at the owner side, false: the owner looks at the student side. */
  previewsOwnerSide: boolean;
}

/**
 * Who may preview which side, and what that does to the interface.
 *
 * Owners preview the student side, then their controls disappear the way a
 * student really sees it. Enrolled people preview the owner side, but only in
 * the demo course and only while they may create modules themselves, because
 * for anyone else the owner side is a set of buttons they will never get.
 * Students get no switch at all.
 */
export function resolvePreview(
  { realIsOwner, isDemoWorkspace, darfModuleAnlegen, override }: PreviewInput,
): PreviewState {
  const canPreview = realIsOwner || (isDemoWorkspace && darfModuleAnlegen);
  const previewsOwnerSide = !realIsOwner;
  // In the demo course the owner preview is on from the start, that is the point of it.
  const previewOn = canPreview && (override ?? (isDemoWorkspace && !realIsOwner));
  const isOwner = realIsOwner ? !previewOn : isDemoWorkspace && previewOn;
  const ownerPreview = !realIsOwner && isDemoWorkspace && previewOn;
  return { canPreview, previewOn, isOwner, ownerPreview, previewsOwnerSide };
}

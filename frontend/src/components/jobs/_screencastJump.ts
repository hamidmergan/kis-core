/** Ob und wie ein Screencast-Job aus der Jobs-Liste heraus im Assistenten geoeffnet wird. */

interface JumpJob {
  tool: string;
  status: string;
  has_download?: boolean;
  render_queued_at?: string | null;
  is_generating_scripts?: boolean;
}

/** "resume" wartet auf eine Eingabe, "open" laeuft oder ist fertig, null hat keine Seite. */
export function screencastJumpKind(job: JumpJob): "resume" | "open" | null {
  if (job.tool !== "screencast_translate") return null;
  if (job.status === "awaiting_user") return job.is_generating_scripts ? null : "resume";
  // Abgelaufene Jobs haben keine Dateien mehr, da gibt es nichts zu zeigen.
  if (job.status === "success") return job.has_download ? "open" : null;
  // Nur die Vertonung hat eine Warteseite, die Uebersetzung nicht.
  if ((job.status === "queued" || job.status === "running") && job.render_queued_at) return "open";
  return null;
}

export function screencastJumpHref(jobUuid: string): string {
  return `/tools/screencast?resume=${jobUuid}`;
}

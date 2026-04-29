import { SCREENCAST_TOOLS, type MyJob } from "../_types";
import { formatDate, formatDuration, toMs } from "../_utils";


export function TimingInfo({ job, isAdmin }: { job: MyJob; isAdmin: boolean }) {
  if (SCREENCAST_TOOLS.has(job.tool)) {
    const queueWaitMs = job.render_queued_at && job.render_started_at
      ? toMs(job.render_started_at) - toMs(job.render_queued_at)
      : null;
    const renderMs = job.render_started_at && job.completed_at
      ? toMs(job.completed_at) - toMs(job.render_started_at)
      : null;
    return (
      <div className="mt-1.5 text-xs text-muted-soft space-y-0.5">
        <p>Eingereicht: {formatDate(job.created_at)}</p>
        {isAdmin && queueWaitMs !== null && (
          <p>Wartezeit: <span className="text-muted">{formatDuration(queueWaitMs)}</span></p>
        )}
        {isAdmin && renderMs !== null && (
          <p>Renderzeit: <span className="text-muted">{formatDuration(renderMs)}</span></p>
        )}
        {job.completed_at && (
          <p>Fertig: {formatDate(job.completed_at)}</p>
        )}
        {job.expires_at && (
          <p>Läuft ab: {formatDate(job.expires_at)}</p>
        )}
      </div>
    );
  }

  const waitMs = job.started_at ? toMs(job.started_at) - toMs(job.created_at) : null;
  const workMs = job.started_at && job.completed_at ? toMs(job.completed_at) - toMs(job.started_at) : null;
  return (
    <div className="mt-1.5 text-xs text-muted-soft space-y-0.5">
      <p>Eingereicht: {formatDate(job.created_at)}</p>
      {isAdmin && waitMs !== null && (
        <p>Wartezeit: <span className="text-muted">{formatDuration(waitMs)}</span></p>
      )}
      {isAdmin && workMs !== null && (
        <p>Bearbeitungszeit: <span className="text-muted">{formatDuration(workMs)}</span></p>
      )}
      {job.completed_at && (
        <p>Fertig: {formatDate(job.completed_at)}</p>
      )}
      {job.expires_at && (
        <p>Läuft ab: {formatDate(job.expires_at)}</p>
      )}
    </div>
  );
}

/** Whether the invite tile shows, and what a dismissal notes down. */

export type EvaluationStand = {
  active?: boolean;
  already_responded?: boolean;
  reveal_round?: number;
  has_activity?: boolean;
};

/** The round a dismissal was noted in, the old note without a round counts as zero. */
function weggeklicktIn(merker: string | null): number {
  if (merker === null) return -1;
  const runde = Number.parseInt(merker, 10);
  return Number.isNaN(runde) ? 0 : runde;
}

export function zeigtEinladung(stand: EvaluationStand | null, merker: string | null): boolean {
  if (!stand?.active || stand.already_responded || !stand.has_activity) return false;
  return (stand.reveal_round ?? 0) > weggeklicktIn(merker);
}

export function merkerFuerRunde(stand: EvaluationStand | null): string {
  return String(stand?.reveal_round ?? 0);
}

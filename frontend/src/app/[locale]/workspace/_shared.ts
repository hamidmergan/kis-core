/** What a link turns its users into, a tutor manages and students only learn. */
type LinkRole = "student" | "tutor";

/** How someone reaches a workspace. Ownership and tutoring both mean "manage". */
export type WorkspaceAccess = "owner" | "tutor" | "student";

export function canManage(access: WorkspaceAccess): boolean {
  return access === "owner" || access === "tutor";
}

export interface AccessLink {
  id: number;
  code: string;
  role?: LinkRole;
  expires_at: string | null;
  created_at?: string | null;
}

export interface KiTutorWorkspace {
  uuid: string;
  title: string;
  description?: string | null;
  status: "pending" | "indexing" | "ready" | "failed";
  source_count: number;
  /** Only set for owner/tutor rows, students never see the count. */
  member_count?: number;
  is_active: boolean;
  access: WorkspaceAccess;
  /** Workspace is shared with tutors, or reached as one. Drives the shared icon. */
  shared: boolean;
  /** Starred by this person, independent of owner/tutor/student access. */
  is_favorite: boolean;
  /** Owned by the demo account, shown alongside the role badge. */
  is_demo_workspace?: boolean;
  /** The demo module the guided tour runs in, at most one carries this. */
  is_tour_module?: boolean;
  access_links?: AccessLink[];
  // Only set for enrolled courses, several links mean several histories.
  enrollment_id?: number | null;
  enrolled_until?: string | null;
  /** Joined through the demo, not through a real link. */
  via_demo?: boolean;
  created_at: string | null;
}

/** A day as 31.12.2026 or 12/31/2026, read in the university's time zone. */
export function formatDay(iso: string, locale: string): string {
  return new Date(iso).toLocaleDateString(locale === "en" ? "en-US" : "de-DE", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    timeZone: "Europe/Berlin",
  });
}

export const MAX_ACCESS_LINKS = 10;
export const MAX_MEMBERS = 100;
export const WORKSPACE_TITLE_MAX = 50;
export const WORKSPACE_DESCRIPTION_MAX = 500;

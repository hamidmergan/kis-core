/** What a link turns its users into, a tutor manages and students only learn. */
export type LinkRole = "student" | "tutor";

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
  is_active: boolean;
  access: WorkspaceAccess;
  /** Workspace is shared with tutors, or reached as one. Drives the shared icon. */
  shared: boolean;
  /** Owned by the demo account, shown alongside the role badge. */
  is_demo_workspace?: boolean;
  access_links?: AccessLink[];
  // Only set for enrolled courses, several links mean several histories.
  enrollment_id?: number | null;
  enrolled_until?: string | null;
  /** Joined through the demo, not through a real link. */
  via_demo?: boolean;
  // Legacy
  enroll_code: string | null;
  enroll_code_expires: string | null;
  created_at: string | null;
}

export interface WorkspaceStats {
  overview: {
    total_enrolled: number;
    active_30d: number;
    total_chat_messages: number;
    total_exercise_sets: number;
  };
}

export const MAX_ACCESS_LINKS = 10;
export const WORKSPACE_TITLE_MAX = 50;
export const WORKSPACE_DESCRIPTION_MAX = 500;

export interface AccessLink {
  id: number;
  code: string;
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
  access_links?: AccessLink[];
  // Legacy
  enroll_code: string | null;
  enroll_code_expires: string | null;
  created_at: string | null;
}

export interface StudentWorkspace {
  uuid: string;
  title: string;
  description?: string | null;
  status: string;
  enrollment_id?: number | null;
  enrolled_until?: string | null;
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
export const WORKSPACE_DESCRIPTION_MAX = 300;

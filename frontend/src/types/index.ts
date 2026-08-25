export type SystemRole = "admin" | "staff" | "user" | "custom";

export interface UserPermissions {
  /** Darf ueberhaupt eine Seite des Adminbereichs sehen, also mindestens ein
   *  Recht aus der Gruppe Einstellungen. Heisst laengst nicht mehr "Admin". */
  allow_admin_panel: boolean;
  allow_aia: boolean;
  allow_workspace_create: boolean;
  tools: string[]; // tool keys
  /** Alle Rechte-Schluessel. Die Seitenleiste entscheidet damit je Seite. */
  keys: string[];
  /** Kein vergebbares Recht, sondern das Recht plus der Serverschalter. */
  allow_ldap_user_create?: boolean;
}

export interface AuthStatus {
  authenticated: boolean;
  local_mode?: boolean;
  user_id?: number;
  username?: string;
  display_name?: string;
  email?: string;
  is_admin?: boolean;
  role?: SystemRole;
  custom_role_id?: number | null;
  permissions?: UserPermissions;
}

export interface LoginResponse {
  status: string;
  username: string;
  display_name: string;
}

export type TTSState = "idle" | "uploading" | "processing" | "done" | "error";

export type ScreencastStep =
  | "upload"
  | "translating"
  | "user-prompt"
  | "translation-review"
  | "preparing"
  | "generating-scripts"
  | "script-review"
  | "tts-settings"
  | "rendering"
  | "done"
  | "error";

export interface GlossaryEntry {
  source: string;
  target: string;
}

export interface Glossary {
  id: string;
  name: string;
  entries: Record<string, string>;
  createdAt: string;
}

export interface SlideData {
  index: number;
  imageBase64: string;
  extractedText: string;
  script: string;
  /** Übersetzung hat den Text dieser Folie nicht verändert. Hinweis, kein Fehler. */
  unchanged?: boolean;
}

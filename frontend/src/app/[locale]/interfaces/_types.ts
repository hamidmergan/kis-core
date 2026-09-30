/** One connected outside voice service of this person. */
export interface OwnInterface {
  id: number;
  vendor: string;
  label: string;
  key_last_chars: string;
  voices: { voice_id: string; name: string }[];
  created_at: string | null;
}

export interface InterfacesOverview {
  consent: { accepted: boolean; accepted_at: string | null; version: number };
  vendors: { key: string; label: string }[];
  interfaces: OwnInterface[];
}

/** What the service still has left, as it reports it. */
export interface Credit {
  used: number;
  limit: number;
  unit: string;
  resets_at: string | null;
}

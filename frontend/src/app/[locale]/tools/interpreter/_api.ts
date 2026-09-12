"use client";

/** Everything the interpreter asks the backend for. */

import { backendApi } from "@/lib/api";
import type { LangCode, Side, Turn } from "./_types";

export type Glossary = Record<string, string> | null;

async function call(path: string, init: RequestInit = {}): Promise<Response> {
  const response = await backendApi.fetch(`/interpreter${path}`, init);
  if (!response.ok) throw new Error(`interpreter ${path} ${response.status}`);
  return response;
}

const asJson = (method: string, body: unknown): RequestInit => ({
  method,
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

export async function translateText(text: string, target: LangCode, providerId: number | null, glossary: Glossary = null): Promise<string> {
  const response = await call("/translate", asJson("POST", {
    text,
    target_lang: target,
    provider_id: providerId != null && providerId > 0 ? providerId : null,
    glossary,
  }));
  const data = (await response.json()) as { text: string };
  return data.text.trim();
}

export async function transcribeWindow(blob: Blob, filename: string, providerId: number | null, language: string): Promise<string> {
  const form = new FormData();
  form.append("audio", blob, filename);
  form.append("language", language);
  if (providerId != null && providerId > 0) form.append("provider_id", String(providerId));
  const response = await call("/transcribe", { method: "POST", body: form });
  const data = (await response.json()) as { text: string };
  return (data.text ?? "").trim();
}

export interface SessionState {
  id: string;
  left_lang: LangCode;
  right_lang: LangCode;
  left_name: string;
  right_name: string;
  ended: boolean;
  created_at: string;
  turns: Turn[];
}

export interface SessionSummary {
  id: string;
  created_at: string;
  updated_at: string;
  ended: boolean;
  left_lang: LangCode;
  right_lang: LangCode;
  left_name: string;
  right_name: string;
  turn_count: number;
  first_original: string;
  first_translation: string;
  first_side: Side;
}

export interface SessionMeta {
  left_lang?: LangCode;
  right_lang?: LangCode;
  left_name?: string;
  right_name?: string;
  ended?: boolean;
}

export async function createSession(meta: SessionMeta): Promise<SessionState> {
  return (await call("/sessions", asJson("POST", meta))).json();
}

export async function listSessions(): Promise<SessionSummary[]> {
  const data = (await (await call("/sessions")).json()) as { sessions: SessionSummary[] };
  return data.sessions;
}

export async function fetchSession(id: string): Promise<SessionState> {
  return (await call(`/sessions/${id}`)).json();
}

export async function patchSession(id: string, meta: SessionMeta): Promise<SessionState> {
  return (await call(`/sessions/${id}`, asJson("PATCH", meta))).json();
}

export async function deleteSession(id: string): Promise<void> {
  await call(`/sessions/${id}`, { method: "DELETE" });
}

/** A sentence goes over as a whole, the server keeps the newest version. */
export async function putTurn(id: string, turn: Turn): Promise<void> {
  await call(`/sessions/${id}/turns/${turn.id}`, asJson("PUT", {
    side: turn.side,
    source: turn.source,
    original: turn.original,
    translation: turn.translation,
    status: turn.status === "transcribing" || turn.status === "pending" ? "translating" : turn.status,
    edited: turn.edited,
    at: turn.at,
  }));
}

import { api } from "./api";
import { invalidateGlossaries } from "@/hooks/_glossaryStore";
import type { AuthStatus, LoginResponse } from "@/types";

let cachedAuth: { result: AuthStatus; timestamp: number } | null = null;
const CACHE_TTL_MS = 5 * 60 * 1000; // 5 minutes

export function clearAuthCache() {
  cachedAuth = null;
  invalidateGlossaries();
}

export async function login(username: string, password: string): Promise<LoginResponse> {
  const result = await api.postJson<LoginResponse>("/auth/login", { username, password });
  clearAuthCache();
  return result;
}

export async function logout(): Promise<void> {
  clearAuthCache();
  await api.postJson("/auth/logout", {});
}

export async function checkAuthStatus(): Promise<AuthStatus> {
  if (cachedAuth && Date.now() - cachedAuth.timestamp < CACHE_TTL_MS) {
    return cachedAuth.result;
  }
  try {
    const result = await api.getJson<AuthStatus>("/auth/status");
    cachedAuth = { result, timestamp: Date.now() };
    return result;
  } catch {
    return { authenticated: false };
  }
}

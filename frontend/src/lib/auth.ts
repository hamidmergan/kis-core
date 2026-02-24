import { api } from "./api";
import type { AuthStatus, LoginResponse } from "@/types";

let cachedAuth: { authenticated: boolean; timestamp: number } | null = null;
const CACHE_TTL_MS = 5 * 60 * 1000; // 5 Minuten

export function clearAuthCache() {
  cachedAuth = null;
}

export async function login(username: string, password: string): Promise<LoginResponse> {
  return api.postJson<LoginResponse>("/auth/login", { username, password });
}

export async function logout(): Promise<void> {
  clearAuthCache();
  await api.postJson("/auth/logout", {});
}

export async function checkAuthStatus(): Promise<AuthStatus> {
  if (cachedAuth && Date.now() - cachedAuth.timestamp < CACHE_TTL_MS) {
    return { authenticated: cachedAuth.authenticated };
  }
  try {
    const result = await api.getJson<AuthStatus>("/auth/status");
    cachedAuth = { authenticated: result.authenticated, timestamp: Date.now() };
    return result;
  } catch {
    return { authenticated: false };
  }
}

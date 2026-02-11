import { api } from "./api";
import type { AuthStatus, LoginResponse } from "@/types";

export async function login(password: string): Promise<LoginResponse> {
  return api.postJson<LoginResponse>("/auth/login", { password });
}

export async function logout(): Promise<void> {
  await api.postJson("/auth/logout", {});
}

export async function checkAuthStatus(): Promise<AuthStatus> {
  try {
    return await api.getJson<AuthStatus>("/auth/status");
  } catch {
    return { authenticated: false };
  }
}

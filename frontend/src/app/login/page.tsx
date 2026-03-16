"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { login, checkAuthStatus } from "@/lib/auth";

export default function LoginPage() {
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [checking, setChecking] = useState(true);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    checkAuthStatus().then((status) => {
      if (status.authenticated) {
        router.replace("/");
      } else {
        setChecking(false);
      }
    });
  }, [router]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      await login(username, password);
      router.refresh();
      router.push("/");
    } catch (err) {
      const message = err instanceof Error ? err.message : "";
      if (message === "account_not_activated") {
        router.push("/pending");
      } else {
        setError("Ungültige Anmeldedaten. Bitte prüfen Sie Benutzername und Passwort.");
      }
    } finally {
      setLoading(false);
    }
  };

  if (checking) return null;

  return (
    <div className="flex items-center justify-center min-h-[80vh] px-4">
      <div className="w-full max-w-sm">
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-8">
          <h1 className="text-2xl font-bold text-[#004261] text-center mb-6">
            <Link href="/" aria-label="Zur Startseite">
              KIS
            </Link>
          </h1>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label htmlFor="username" className="block text-sm font-medium text-gray-700 mb-1">
                Benutzername
              </label>
              <input
                id="username"
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                autoComplete="username"
                required
                disabled={loading}
                className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-[#004261] focus:border-transparent disabled:opacity-50"
              />
            </div>

            <div>
              <label htmlFor="password" className="block text-sm font-medium text-gray-700 mb-1">
                Passwort
              </label>
              <input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="current-password"
                required
                disabled={loading}
                aria-describedby={error ? "login-error" : undefined}
                className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-[#004261] focus:border-transparent disabled:opacity-50"
              />
            </div>

            {error && (
              <p id="login-error" className="text-sm text-red-600" role="alert">
                {error}
              </p>
            )}

            <button
              type="submit"
              disabled={loading || !username || !password}
              aria-label="Anmelden"
              className="w-full px-4 py-2 bg-[#004261] text-white text-sm font-medium rounded-md hover:bg-[#003a56] disabled:opacity-50 disabled:cursor-not-allowed focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#004261] transition-colors"
            >
              {loading ? "Wird angemeldet..." : "Anmelden"}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}

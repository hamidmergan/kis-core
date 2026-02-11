"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { login } from "@/lib/auth";

export default function LoginPage() {
  const router = useRouter();
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      await login(password);
      router.push("/");
    } catch {
      setError("Falsches Passwort");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex items-center justify-center min-h-[80vh] px-4">
      <div className="w-full max-w-sm">
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-8">
          <h1 className="text-2xl font-bold text-[#0066cc] text-center mb-2">
            <Link href="/" aria-label="Zur Startseite">
              KIS-THL
            </Link>
          </h1>
          <p className="text-sm text-gray-500 text-center mb-8">Dokumentübersetzung</p>

          <form onSubmit={handleSubmit}>
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
              className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-[#0066cc] focus:border-transparent disabled:opacity-50"
            />

            {error && (
              <p id="login-error" className="mt-2 text-sm text-red-600" role="alert">
                {error}
              </p>
            )}

            <button
              type="submit"
              disabled={loading || !password}
              aria-label="Anmelden"
              className="mt-4 w-full px-4 py-2 bg-[#0066cc] text-white text-sm font-medium rounded-md hover:bg-[#0055aa] disabled:opacity-50 disabled:cursor-not-allowed focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#0066cc] transition-colors"
            >
              {loading ? "Wird angemeldet..." : "Anmelden"}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}

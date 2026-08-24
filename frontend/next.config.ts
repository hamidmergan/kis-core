import type { NextConfig } from "next";
import createNextIntlPlugin from "next-intl/plugin";

const withNextIntl = createNextIntlPlugin("./src/i18n/request.ts");

const backendUrl = process.env.BACKEND_URL || "http://localhost:8000";

const nextConfig: NextConfig = {
  output: "standalone",
  // Ein Probe-Build darf den laufenden Dev-Server nicht abschiessen: beide
  // schreiben sonst in dasselbe .next und :3000 ist danach kaputt. Mit
  // NEXT_DIST_DIR=.next-verify baut die Probe daneben. Next schreibt dabei
  // next-env.d.ts und tsconfig.json auf den Probe-Ordner um, die beiden also
  // hinterher zuruecksetzen (git checkout).
  ...(process.env.NEXT_DIST_DIR ? { distDir: process.env.NEXT_DIST_DIR } : {}),
  reactStrictMode: true,
  webpack: (config) => {
    // Required for react-pdf (pdfjs-dist uses canvas which doesn't exist in SSR)
    config.resolve.alias.canvas = false;
    return config;
  },
  experimental: {
    middlewareClientMaxBodySize: "500mb",
    proxyTimeout: 600000, // 10 min – für lokale Ollama-Generierung
    optimizePackageImports: ["@phosphor-icons/react"],
  },
  async redirects() {
    // Alte Adresse der Kalender-Seite, damit gemerkte Links weiter ankommen.
    return [
      { source: "/schedule", destination: "/kalender", permanent: false },
      { source: "/:locale(de|en)/schedule", destination: "/:locale/kalender", permanent: false },
    ];
  },
  async rewrites() {
    return [
      {
        source: "/auth/:path*",
        destination: `${backendUrl}/auth/:path*`,
      },
      {
        source: "/health",
        destination: `${backendUrl}/health`,
      },
      {
        source: "/api/health/maintenance",
        destination: `${backendUrl}/health/maintenance`,
      },
      {
        source: "/api/health/labels",
        destination: `${backendUrl}/health/labels`,
      },
      {
        source: "/translate/config",
        destination: `${backendUrl}/translate/config`,
      },
      {
        source: "/api/translate/config",
        destination: `${backendUrl}/translate/config`,
      },
      {
        source: "/translate",
        destination: `${backendUrl}/translate`,
      },
      {
        source: "/translate-document",
        destination: `${backendUrl}/translate-document`,
      },
      {
        source: "/api/tts/providers-with-voices",
        destination: `${backendUrl}/tts/providers-with-voices`,
      },
      {
        source: "/api/tts/providers/:id/preview",
        destination: `${backendUrl}/tts/providers/:id/preview`,
      },
      {
        source: "/api/tts/providers",
        destination: `${backendUrl}/tts/providers`,
      },
      {
        source: "/api/tts",
        destination: `${backendUrl}/tts`,
      },
      {
        source: "/api/voices",
        destination: `${backendUrl}/voices`,
      },
      {
        source: "/api/admin/:path*",
        destination: `${backendUrl}/admin/:path*`,
      },
      {
        source: "/api/me/:path*",
        destination: `${backendUrl}/me/:path*`,
      },
      {
        source: "/api/me",
        destination: `${backendUrl}/me`,
      },
      {
        source: "/api/glossaries/:path*",
        destination: `${backendUrl}/glossaries/:path*`,
      },
      {
        source: "/api/glossaries",
        destination: `${backendUrl}/glossaries`,
      },
      {
        source: "/api/jobs/my",
        destination: `${backendUrl}/jobs/my`,
      },
      {
        source: "/api/jobs/stream",
        destination: `${backendUrl}/jobs/stream`,
      },
      {
        source: "/api/jobs/check/:tool_group",
        destination: `${backendUrl}/jobs/check/:tool_group`,
      },
      {
        source: "/api/jobs/:job_uuid",
        destination: `${backendUrl}/jobs/:job_uuid`,
      },
      {
        source: "/api/jobs/:job_uuid/download",
        destination: `${backendUrl}/jobs/:job_uuid/download`,
      },
      {
        source: "/api/jobs/:job_uuid/pptx",
        destination: `${backendUrl}/jobs/:job_uuid/pptx`,
      },
      {
        source: "/api/jobs/:job_uuid/bundle",
        destination: `${backendUrl}/jobs/:job_uuid/bundle`,
      },
      {
        source: "/api/jobs/:job_uuid/subtitles",
        destination: `${backendUrl}/jobs/:job_uuid/subtitles`,
      },
      {
        source: "/api/jobs/:job_uuid/video",
        destination: `${backendUrl}/jobs/:job_uuid/video`,
      },
      {
        source: "/api/jobs/:job_uuid/cancel",
        destination: `${backendUrl}/jobs/:job_uuid/cancel`,
      },
      {
        source: "/api/jobs/:job_uuid/retry",
        destination: `${backendUrl}/jobs/:job_uuid/retry`,
      },
      {
        source: "/api/transcription/providers",
        destination: `${backendUrl}/transcription/providers`,
      },
      {
        source: "/api/transcription",
        destination: `${backendUrl}/transcription`,
      },
      {
        source: "/api/summary/providers",
        destination: `${backendUrl}/summary/providers`,
      },
      {
        source: "/api/summary",
        destination: `${backendUrl}/summary`,
      },
      {
        source: "/api/image/:path*",
        destination: `${backendUrl}/image/:path*`,
      },
      {
        source: "/api/script",
        destination: `${backendUrl}/script`,
      },
      {
        source: "/api/screencast",
        destination: `${backendUrl}/screencast`,
      },
      {
        source: "/api/screencast/:path*",
        destination: `${backendUrl}/screencast/:path*`,
      },
      {
        source: "/api/screencast-demo/:path*",
        destination: `${backendUrl}/screencast-demo/:path*`,
      },
      {
        source: "/api/ai-assistant/:path*",
        destination: `${backendUrl}/ai-assistant/:path*`,
      },
      {
        source: "/docs",
        destination: `${backendUrl}/docs`,
      },
      {
        source: "/redoc",
        destination: `${backendUrl}/redoc`,
      },
      {
        source: "/openapi.json",
        destination: `${backendUrl}/openapi.json`,
      },
    ];
  },
};

export default withNextIntl(nextConfig);

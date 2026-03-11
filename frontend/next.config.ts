import type { NextConfig } from "next";

const backendUrl = process.env.BACKEND_URL || "http://localhost:8000";

const nextConfig: NextConfig = {
  output: "standalone",
  reactStrictMode: true,
  experimental: {
    middlewareClientMaxBodySize: "500mb",
    proxyTimeout: 600000, // 10 min – für lokale Ollama-Generierung
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
        source: "/translate/config",
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
        source: "/api/tts/providers",
        destination: `${backendUrl}/tts/providers`,
      },
      {
        source: "/api/tts",
        destination: `${backendUrl}/tts`,
      },
      {
        source: "/api/kokoro/voices",
        destination: `${backendUrl}/kokoro/voices`,
      },
      {
        source: "/api/kokoro/preview",
        destination: `${backendUrl}/kokoro/preview`,
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
        source: "/api/jobs/:job_uuid/cancel",
        destination: `${backendUrl}/jobs/:job_uuid/cancel`,
      },
      {
        source: "/api/jobs/:job_uuid/retry",
        destination: `${backendUrl}/jobs/:job_uuid/retry`,
      },
      {
        source: "/api/script",
        destination: `${backendUrl}/script`,
      },
      {
        source: "/api/video-dubbing",
        destination: `${backendUrl}/video-dubbing`,
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

export default nextConfig;
